from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd


def run_sql_reports(
    sql_dir: Path,
    output_dir: Path,
    lines: pd.DataFrame,
    invoices: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """Execute the visible portfolio SQL against the same validated frames."""
    connection = duckdb.connect(":memory:")
    connection.register("invoice_lines", lines)
    connection.register("purchase_invoices", invoices)
    output_dir.mkdir(parents=True, exist_ok=True)
    reports: dict[str, pd.DataFrame] = {}
    try:
        for path in sorted(sql_dir.glob("*.sql")):
            result = connection.execute(path.read_text(encoding="utf-8")).fetchdf()
            reports[path.stem] = result
            result.to_csv(output_dir / f"{path.stem}.csv", index=False)
    finally:
        connection.close()
    return reports
