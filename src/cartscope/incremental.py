from __future__ import annotations

from pathlib import Path
from typing import Self

import duckdb
import pandas as pd

BUSINESS_COLUMNS = [
    "InvoiceNo",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "UnitPrice",
    "CustomerID",
    "Country",
]
METADATA_COLUMNS = ["source_event_id", "source_updated_at", "source_deleted"]
ALL_COLUMNS = [*BUSINESS_COLUMNS, *METADATA_COLUMNS]


class IncrementalTransactionStore:
    """Append source versions and update only affected current-state rows."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = duckdb.connect(str(path))
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS raw_transaction_versions (
                InvoiceNo VARCHAR,
                StockCode VARCHAR,
                Description VARCHAR,
                Quantity BIGINT,
                InvoiceDate TIMESTAMP,
                UnitPrice DOUBLE,
                CustomerID VARCHAR,
                Country VARCHAR,
                source_event_id VARCHAR NOT NULL,
                source_updated_at TIMESTAMP NOT NULL,
                source_deleted BOOLEAN NOT NULL,
                ingestion_batch_id VARCHAR NOT NULL,
                PRIMARY KEY (source_event_id, source_updated_at)
            );
            CREATE TABLE IF NOT EXISTS current_transactions AS
            SELECT * EXCLUDE (ingestion_batch_id)
            FROM raw_transaction_versions
            WHERE FALSE;
            """
        )

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @staticmethod
    def _validate(frame: pd.DataFrame) -> pd.DataFrame:
        missing = set(ALL_COLUMNS).difference(frame.columns)
        if missing:
            raise ValueError(f"Missing incremental columns: {sorted(missing)}")
        if frame[["source_event_id", "source_updated_at"]].isna().any().any():
            raise ValueError("Source event identity and update time cannot be null")
        if frame.duplicated(["source_event_id", "source_updated_at"]).any():
            raise ValueError("One batch contains duplicate source event versions")
        validated = frame[ALL_COLUMNS].copy()
        validated["source_updated_at"] = pd.to_datetime(validated["source_updated_at"], utc=False)
        validated["InvoiceDate"] = pd.to_datetime(validated["InvoiceDate"], utc=False)
        validated["source_deleted"] = validated["source_deleted"].astype(bool)
        return validated

    def ingest(self, frame: pd.DataFrame, batch_id: str) -> dict[str, int]:
        if not batch_id.strip():
            raise ValueError("batch_id must not be empty")
        incoming = self._validate(frame).assign(ingestion_batch_id=batch_id)
        self.connection.register("incoming_versions", incoming)
        before_versions = int(
            self.connection.execute("SELECT count(*) FROM raw_transaction_versions").fetchone()[0]
        )
        try:
            self.connection.execute("BEGIN TRANSACTION")
            self.connection.execute(
                """
                INSERT INTO raw_transaction_versions
                SELECT * FROM incoming_versions
                ON CONFLICT (source_event_id, source_updated_at) DO NOTHING
                """
            )
            self.connection.execute(
                """
                DELETE FROM current_transactions
                WHERE source_event_id IN (SELECT DISTINCT source_event_id FROM incoming_versions)
                """
            )
            self.connection.execute(
                """
                INSERT INTO current_transactions
                SELECT * EXCLUDE (ingestion_batch_id, version_rank)
                FROM (
                    SELECT *, row_number() OVER (
                        PARTITION BY source_event_id
                        ORDER BY source_updated_at DESC, ingestion_batch_id DESC
                    ) AS version_rank
                    FROM raw_transaction_versions
                    WHERE source_event_id IN (
                        SELECT DISTINCT source_event_id FROM incoming_versions
                    )
                )
                WHERE version_rank = 1 AND NOT source_deleted
                """
            )
            self.connection.execute("COMMIT")
        except Exception:
            self.connection.execute("ROLLBACK")
            raise
        finally:
            self.connection.unregister("incoming_versions")
        after_versions = int(
            self.connection.execute("SELECT count(*) FROM raw_transaction_versions").fetchone()[0]
        )
        current_rows = int(
            self.connection.execute("SELECT count(*) FROM current_transactions").fetchone()[0]
        )
        return {
            "received_versions": len(incoming),
            "inserted_versions": after_versions - before_versions,
            "replayed_versions": len(incoming) - (after_versions - before_versions),
            "affected_events": incoming["source_event_id"].nunique(),
            "current_rows": current_rows,
        }

    def current_frame(self) -> pd.DataFrame:
        return self.connection.execute(
            "SELECT * FROM current_transactions ORDER BY source_event_id"
        ).fetchdf()

    def full_rebuild_frame(self) -> pd.DataFrame:
        return self.connection.execute(
            """
            SELECT * EXCLUDE (ingestion_batch_id, version_rank)
            FROM (
                SELECT *, row_number() OVER (
                    PARTITION BY source_event_id
                    ORDER BY source_updated_at DESC, ingestion_batch_id DESC
                ) AS version_rank
                FROM raw_transaction_versions
            )
            WHERE version_rank = 1 AND NOT source_deleted
            ORDER BY source_event_id
            """
        ).fetchdf()

    def reconciliation(self) -> dict[str, int | float]:
        row = self.connection.execute(
            """
            SELECT
                (SELECT count(*) FROM raw_transaction_versions) AS stored_versions,
                (SELECT count(*) FROM current_transactions) AS current_rows,
                (SELECT count(*) FROM (
                    SELECT source_event_id FROM raw_transaction_versions
                    GROUP BY source_event_id HAVING count(*) > 1
                )) AS corrected_events,
                (SELECT count(*) FROM (
                    SELECT source_event_id, arg_max(source_deleted, source_updated_at) AS deleted
                    FROM raw_transaction_versions GROUP BY source_event_id
                ) WHERE deleted) AS deleted_events,
                (SELECT coalesce(sum(Quantity * UnitPrice), 0) FROM current_transactions)
                    AS current_gross_value
            """
        ).fetchone()
        return {
            "stored_versions": int(row[0]),
            "current_rows": int(row[1]),
            "corrected_events": int(row[2]),
            "deleted_events": int(row[3]),
            "current_gross_value": float(row[4]),
        }
