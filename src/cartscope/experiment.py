from __future__ import annotations

from dataclasses import asdict, dataclass
from math import erfc, sqrt
from statistics import NormalDist
from typing import Any

import pandas as pd

from .analytics import wilson_interval


@dataclass(frozen=True)
class ExperimentSpec:
    """Pre-declared rules for a two-arm customer-level retention experiment."""

    control_label: str = "control"
    treatment_label: str = "treatment"
    expected_treatment_share: float = 0.5
    alpha: float = 0.05
    srm_alpha: float = 0.01
    minimum_absolute_lift: float = 0.05

    def validate(self) -> None:
        if not 0 < self.expected_treatment_share < 1:
            raise ValueError("expected_treatment_share must be between 0 and 1")
        if not 0 < self.alpha < 1:
            raise ValueError("alpha must be between 0 and 1")
        if not 0 < self.srm_alpha < 1:
            raise ValueError("srm_alpha must be between 0 and 1")
        if not 0 <= self.minimum_absolute_lift <= 1:
            raise ValueError("minimum_absolute_lift must be between 0 and 1")
        if self.control_label == self.treatment_label:
            raise ValueError("control and treatment labels must differ")


def _validate_assignments(frame: pd.DataFrame, spec: ExperimentSpec) -> pd.DataFrame:
    required = {"customer_id", "variant", "purchased_60d"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Experiment data is missing required columns: {missing}")
    if frame[sorted(required)].isna().any().any():
        raise ValueError("Experiment data contains missing assignment or outcome values")
    if frame["customer_id"].duplicated().any():
        raise ValueError("Each customer must appear exactly once for intent-to-treat analysis")

    expected_variants = {spec.control_label, spec.treatment_label}
    observed_variants = set(frame["variant"].astype(str))
    if observed_variants != expected_variants:
        raise ValueError(
            f"Expected variants {sorted(expected_variants)}, got {sorted(observed_variants)}"
        )
    outcomes = pd.to_numeric(frame["purchased_60d"], errors="coerce")
    if outcomes.isna().any() or not outcomes.isin([0, 1]).all():
        raise ValueError("purchased_60d must contain only 0/1 values")

    validated = frame.copy()
    validated["variant"] = validated["variant"].astype(str)
    validated["purchased_60d"] = outcomes.astype(int)
    return validated


def _srm_test(control_count: int, treatment_count: int, treatment_share: float) -> dict[str, float]:
    """Pearson chi-square sample-ratio-mismatch test for two assignment arms."""
    total = control_count + treatment_count
    expected_treatment = total * treatment_share
    expected_control = total - expected_treatment
    chi_square = (
        (control_count - expected_control) ** 2 / expected_control
        + (treatment_count - expected_treatment) ** 2 / expected_treatment
    )
    # A chi-square distribution with one degree of freedom has this survival function.
    p_value = erfc(sqrt(chi_square / 2))
    return {"chi_square": chi_square, "p_value": p_value}


def _arm_summary(frame: pd.DataFrame, label: str, alpha: float) -> dict[str, float | int]:
    arm = frame[frame["variant"] == label]
    customers = len(arm)
    purchasers = int(arm["purchased_60d"].sum())
    rate = purchasers / customers
    z = 1.959963984540054 if alpha == 0.05 else NormalDist().inv_cdf(1 - alpha / 2)
    ci_low, ci_high = wilson_interval(purchasers, customers, z=z)
    return {
        "customers": customers,
        "purchasers": purchasers,
        "rate": rate,
        "ci_low": ci_low,
        "ci_high": ci_high,
    }


def analyze_retention_experiment(
    frame: pd.DataFrame, spec: ExperimentSpec | None = None
) -> dict[str, Any]:
    """Analyse a two-arm experiment using customer-level intent to treat.

    The absolute-lift interval uses Newcombe's method based on independent
    Wilson intervals. A failed sample-ratio check invalidates the ship decision.
    """
    spec = spec or ExperimentSpec()
    spec.validate()
    validated = _validate_assignments(frame, spec)
    control = _arm_summary(validated, spec.control_label, spec.alpha)
    treatment = _arm_summary(validated, spec.treatment_label, spec.alpha)
    srm = _srm_test(
        int(control["customers"]),
        int(treatment["customers"]),
        spec.expected_treatment_share,
    )

    control_rate = float(control["rate"])
    treatment_rate = float(treatment["rate"])
    absolute_lift = treatment_rate - control_rate
    lift_low = absolute_lift - sqrt(
        (treatment_rate - float(treatment["ci_low"])) ** 2
        + (float(control["ci_high"]) - control_rate) ** 2
    )
    lift_high = absolute_lift + sqrt(
        (float(treatment["ci_high"]) - treatment_rate) ** 2
        + (control_rate - float(control["ci_low"])) ** 2
    )

    if srm["p_value"] < spec.srm_alpha:
        decision = "invalid_sample_ratio"
    elif lift_low > 0 and absolute_lift >= spec.minimum_absolute_lift:
        decision = "primary_metric_pass"
    else:
        decision = "do_not_ship_primary"

    return {
        "spec": asdict(spec),
        "control": control,
        "treatment": treatment,
        "absolute_lift": absolute_lift,
        "relative_lift": absolute_lift / control_rate if control_rate else None,
        "absolute_lift_ci_low": max(-1.0, lift_low),
        "absolute_lift_ci_high": min(1.0, lift_high),
        "sample_ratio_mismatch": srm,
        "decision": decision,
        "requires_guardrail_review": decision == "primary_metric_pass",
        "decision_rule": (
            "the primary metric passes only when SRM p-value is at least srm_alpha, the lift "
            "interval excludes zero, and observed absolute lift meets minimum_absolute_lift; "
            "a final ship decision also requires separately approved guardrails"
        ),
    }
