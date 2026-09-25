from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import yaml

from .experiment import ExperimentSpec, analyze_retention_experiment


def load_spec(path: Path) -> ExperimentSpec:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    analysis = raw["analysis"]
    return ExperimentSpec(
        control_label=str(analysis["control_label"]),
        treatment_label=str(analysis["treatment_label"]),
        expected_treatment_share=float(analysis["expected_treatment_share"]),
        alpha=float(analysis["alpha"]),
        srm_alpha=float(analysis["srm_alpha"]),
        minimum_absolute_lift=float(analysis["minimum_absolute_lift"]),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyse a CartScope retention experiment")
    parser.add_argument("--input", type=Path, required=True, help="CSV with customer_id, variant and purchased_60d")
    parser.add_argument("--config", type=Path, default=Path("configs/retention_experiment.yaml"))
    parser.add_argument("--output", type=Path, default=Path("outputs/experiment/result.json"))
    args = parser.parse_args()

    result = analyze_retention_experiment(pd.read_csv(args.input), load_spec(args.config))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
