from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import yaml

from cartscope.analytics import (
    AnalysisConfig,
    cleaning_ledger,
    cohort_retention,
    experiment_power_grid,
    prepare_lines,
    purchase_invoices,
    repeat_purchase_60d,
    segment_customers,
)
from cartscope.data import demo_transactions, load_transactions, sha256_file
from cartscope.report import write_report
from cartscope.sql_analysis import run_sql_reports


def run(input_path: Path | None, config_path: Path, output_dir: Path) -> None:
    raw_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config = AnalysisConfig(
        analysis_end=pd.Timestamp(raw_config["analysis_end"]),
        repeat_window_days=int(raw_config["repeat_window_days"]),
        snapshot_date=pd.Timestamp(raw_config["snapshot_date"]),
        followup_days=int(raw_config["followup_days"]),
        segment_quantile=float(raw_config["segment_quantile"]),
    )
    frame = load_transactions(input_path) if input_path else demo_transactions()
    lines = prepare_lines(frame)
    invoices = purchase_invoices(lines)
    ledger = cleaning_ledger(lines)
    cohorts = cohort_retention(invoices)
    repeat = repeat_purchase_60d(invoices, config.analysis_end, config.repeat_window_days)
    segments, outcomes = segment_customers(invoices, config)
    write_report(output_dir, ledger, cohorts, repeat, segments, outcomes, experiment_power_grid())
    run_sql_reports(Path("sql"), output_dir / "sql", lines, invoices)
    manifest = {
        "mode": "real" if input_path else "demo",
        "input": str(input_path) if input_path else "built-in deterministic fixture",
        "sha256": sha256_file(input_path) if input_path else None,
        "rows": len(frame),
        "purchase_invoices": len(invoices),
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"output_dir": str(output_dir), **manifest, "repeat_purchase": repeat}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CartScope retention analysis")
    parser.add_argument("--input", type=Path, help="UCI Online Retail workbook, CSV, or Parquet")
    parser.add_argument("--config", type=Path, default=Path("configs/analysis.yaml"))
    parser.add_argument("--output", type=Path, default=Path("outputs/demo"))
    args = parser.parse_args()
    run(args.input, args.config, args.output)


if __name__ == "__main__":
    main()
