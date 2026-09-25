-- Reconcile the append-only source history with the incrementally maintained current table.
WITH latest AS (
    SELECT
        *,
        row_number() OVER (
            PARTITION BY source_event_id
            ORDER BY source_updated_at DESC, ingestion_batch_id DESC
        ) AS version_rank
    FROM raw_transaction_versions
), rebuilt AS (
    SELECT * EXCLUDE (ingestion_batch_id, version_rank)
    FROM latest
    WHERE version_rank = 1 AND NOT source_deleted
), differences AS (
    (SELECT * FROM rebuilt EXCEPT SELECT * FROM current_transactions)
    UNION ALL
    (SELECT * FROM current_transactions EXCEPT SELECT * FROM rebuilt)
)
SELECT
    (SELECT count(*) FROM raw_transaction_versions) AS stored_versions,
    (SELECT count(*) FROM current_transactions) AS current_rows,
    (SELECT count(*) FROM differences) AS incremental_full_rebuild_differences;
