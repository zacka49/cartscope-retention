from __future__ import annotations

import pandas as pd
import pytest

from cartscope.experiment import ExperimentSpec, analyze_retention_experiment


def assignments(control: tuple[int, int], treatment: tuple[int, int]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for variant, (customers, purchasers) in (("control", control), ("treatment", treatment)):
        for index in range(customers):
            rows.append(
                {
                    "customer_id": f"{variant}-{index}",
                    "variant": variant,
                    "purchased_60d": int(index < purchasers),
                }
            )
    return pd.DataFrame(rows)


def test_material_significant_lift_passes_primary_gate() -> None:
    result = analyze_retention_experiment(assignments((400, 80), (400, 140)))

    assert result["absolute_lift"] == pytest.approx(0.15)
    assert result["absolute_lift_ci_low"] > 0
    assert result["decision"] == "primary_metric_pass"
    assert result["requires_guardrail_review"] is True


def test_null_result_is_not_shipped() -> None:
    result = analyze_retention_experiment(assignments((400, 120), (400, 124)))

    assert result["absolute_lift_ci_low"] < 0
    assert result["decision"] == "do_not_ship_primary"


def test_sample_ratio_mismatch_invalidates_result() -> None:
    result = analyze_retention_experiment(assignments((190, 38), (10, 8)))

    assert result["sample_ratio_mismatch"]["p_value"] < 0.01
    assert result["decision"] == "invalid_sample_ratio"


def test_duplicate_customer_breaks_intent_to_treat_contract() -> None:
    frame = assignments((10, 2), (10, 4))
    frame.loc[1, "customer_id"] = frame.loc[0, "customer_id"]

    with pytest.raises(ValueError, match="exactly once"):
        analyze_retention_experiment(frame, ExperimentSpec())
