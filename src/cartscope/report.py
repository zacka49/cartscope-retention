from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd


def write_report(output_dir: Path, ledger: pd.DataFrame, cohorts: pd.DataFrame, repeat: dict[str, object], segments: pd.DataFrame, outcomes: pd.DataFrame, power: pd.DataFrame) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger.to_csv(output_dir / "cleaning_ledger.csv", index=False)
    cohorts.to_csv(output_dir / "cohort_retention.csv", index=False)
    segments.to_csv(output_dir / "customer_segments.csv", index=False)
    outcomes.to_csv(output_dir / "segment_outcomes.csv", index=False)
    power.to_csv(output_dir / "experiment_power.csv", index=False)
    (output_dir / "repeat_purchase.json").write_text(json.dumps(repeat, indent=2), encoding="utf-8")
    body = "".join(
        [
            "<h1>CartScope retention report</h1>",
            "<p>Historical, observational analysis. Segment differences are not causal effects.</p>",
            "<h2>Data reconciliation</h2>",
            ledger.to_html(index=False, border=0),
            "<h2>60-day repeat purchase</h2>",
            f"<pre>{html.escape(json.dumps(repeat, indent=2))}</pre>",
            "<h2>Segment outcomes</h2>",
            outcomes.to_html(index=False, border=0),
            "<h2>Proposed experiment sample sizes</h2>",
            "<p>Assumptions only: two-sided 5% significance and 80% power.</p>",
            power.to_html(index=False, border=0),
            "<h2>Cohort retention</h2>",
            cohorts.to_html(index=False, border=0),
        ]
    )
    (output_dir / "report.html").write_text(f"<!doctype html><meta charset='utf-8'><title>CartScope</title>{body}", encoding="utf-8")
