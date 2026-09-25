from pathlib import Path

import pandas as pd

from cartscope.incremental import IncrementalTransactionStore


def events() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "InvoiceNo": "1001",
                "StockCode": "A",
                "Description": "Notebook",
                "Quantity": 1,
                "InvoiceDate": "2011-01-01",
                "UnitPrice": 10.0,
                "CustomerID": "C1",
                "Country": "United Kingdom",
                "source_event_id": "line-1",
                "source_updated_at": "2011-01-01 10:00:00",
                "source_deleted": False,
            },
            {
                "InvoiceNo": "1002",
                "StockCode": "B",
                "Description": "Pen",
                "Quantity": 2,
                "InvoiceDate": "2011-01-02",
                "UnitPrice": 2.0,
                "CustomerID": "C2",
                "Country": "United Kingdom",
                "source_event_id": "line-2",
                "source_updated_at": "2011-01-02 10:00:00",
                "source_deleted": False,
            },
        ]
    )


def test_replay_corrections_late_credits_and_deletes_match_full_rebuild(tmp_path: Path) -> None:
    with IncrementalTransactionStore(tmp_path / "warehouse.duckdb") as store:
        first = store.ingest(events(), "initial")
        replay = store.ingest(events(), "initial-replay")
        assert first["inserted_versions"] == 2
        assert replay["inserted_versions"] == 0
        assert replay["replayed_versions"] == 2

        correction = events().iloc[[0]].copy()
        correction["Quantity"] = 3
        correction["source_updated_at"] = "2011-01-03 09:00:00"
        store.ingest(correction, "correction")

        credit = events().iloc[[0]].copy()
        credit["InvoiceNo"] = "C1001"
        credit["Quantity"] = -1
        credit["source_event_id"] = "credit-1"
        credit["source_updated_at"] = "2011-01-05 09:00:00"
        store.ingest(credit, "late-credit")

        deletion = events().iloc[[1]].copy()
        deletion["source_deleted"] = True
        deletion["source_updated_at"] = "2011-01-06 09:00:00"
        store.ingest(deletion, "source-delete")

        current = store.current_frame()
        rebuilt = store.full_rebuild_frame()
        pd.testing.assert_frame_equal(current, rebuilt)
        assert set(current["source_event_id"]) == {"line-1", "credit-1"}
        assert current.loc[current["source_event_id"] == "line-1", "Quantity"].item() == 3

        reconciliation = store.reconciliation()
        assert reconciliation == {
            "stored_versions": 5,
            "current_rows": 2,
            "corrected_events": 2,
            "deleted_events": 1,
            "current_gross_value": 20.0,
        }
