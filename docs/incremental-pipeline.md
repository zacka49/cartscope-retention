# Incremental transaction pipeline

The optional DuckDB store models a source that supplies a stable `source_event_id`, a source-controlled `source_updated_at`, and deletion tombstones. It keeps an append-only version table and refreshes only current-state rows affected by each batch.

The integration test covers four operational cases: replaying the same versions, receiving a correction to an existing event, receiving a late credit, and deleting a source event. It then proves that the incrementally maintained table is identical to a full latest-version rebuild and reconciles row counts and gross value.

This contract intentionally does not invent a reliable event ID for the UCI workbook. A hash of all row values can make exact file replays idempotent, but it cannot distinguish a legitimate identical line from a duplicate or connect a correction to the original row. A production source must provide a stable key/change sequence, or the ingestion adapter must define one with the source owner.

`sql/incremental/reconciliation.sql` is the visible SQL audit. A deployed warehouse would also record batch manifests, source watermarks, schema versions, rejected rows and operational alerts.
