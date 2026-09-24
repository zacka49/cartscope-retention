from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from statistics import NormalDist

import pandas as pd


@dataclass(frozen=True)
class AnalysisConfig:
    analysis_end: pd.Timestamp
    repeat_window_days: int = 60
    snapshot_date: pd.Timestamp = field(default_factory=lambda: pd.Timestamp("2011-10-01"))
    followup_days: int = 60
    segment_quantile: float = 0.75


def prepare_lines(frame: pd.DataFrame) -> pd.DataFrame:
    lines = frame.copy()
    lines["InvoiceNo"] = lines["InvoiceNo"].astype("string").str.strip()
    lines["StockCode"] = lines["StockCode"].astype("string").str.strip()
    lines["CustomerID"] = lines["CustomerID"].astype("string").str.replace(r"\.0$", "", regex=True)
    lines["InvoiceDate"] = pd.to_datetime(lines["InvoiceDate"], errors="coerce")
    lines["Quantity"] = pd.to_numeric(lines["Quantity"], errors="coerce")
    lines["UnitPrice"] = pd.to_numeric(lines["UnitPrice"], errors="coerce")
    lines["line_value"] = lines["Quantity"] * lines["UnitPrice"]
    lines["is_cancel_invoice"] = lines["InvoiceNo"].str.upper().str.startswith("C", na=False)
    invalid = lines[["InvoiceNo", "StockCode", "InvoiceDate", "Quantity", "UnitPrice"]].isna().any(axis=1)
    lines["line_status"] = "purchase"
    lines.loc[lines["is_cancel_invoice"] | (lines["Quantity"] < 0), "line_status"] = "credit"
    lines.loc[(lines["UnitPrice"] <= 0) & ~invalid, "line_status"] = "adjustment"
    lines.loc[invalid, "line_status"] = "invalid"
    lines["is_identified"] = lines["CustomerID"].notna()
    return lines


def cleaning_ledger(lines: pd.DataFrame) -> pd.DataFrame:
    return (
        lines.groupby("line_status", dropna=False)
        .agg(rows=("InvoiceNo", "size"), signed_value=("line_value", "sum"))
        .reset_index()
        .sort_values("line_status")
    )


def purchase_invoices(lines: pd.DataFrame) -> pd.DataFrame:
    eligible = lines[(lines["line_status"] == "purchase") & lines["is_identified"]].copy()
    return (
        eligible.groupby(["InvoiceNo", "CustomerID", "Country"], as_index=False)
        .agg(invoice_date=("InvoiceDate", "min"), order_value=("line_value", "sum"), units=("Quantity", "sum"))
        .sort_values(["CustomerID", "invoice_date", "InvoiceNo"])
        .reset_index(drop=True)
    )


def cohort_retention(invoices: pd.DataFrame) -> pd.DataFrame:
    work = invoices.copy()
    work["order_month"] = work["invoice_date"].dt.to_period("M")
    first = work.groupby("CustomerID")["order_month"].min().rename("cohort_month")
    work = work.join(first, on="CustomerID")
    work["month_number"] = (
        (work["order_month"].dt.year - work["cohort_month"].dt.year) * 12
        + work["order_month"].dt.month
        - work["cohort_month"].dt.month
    )
    cohort_sizes = first.value_counts().rename("cohort_size")
    active = (
        work.groupby(["cohort_month", "month_number"])["CustomerID"]
        .nunique()
        .rename("active_customers")
        .reset_index()
    )
    active = active.join(cohort_sizes, on="cohort_month")
    active["retention_rate"] = active["active_customers"] / active["cohort_size"]
    active["cohort_month"] = active["cohort_month"].astype(str)
    return active.sort_values(["cohort_month", "month_number"])


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total <= 0:
        return (float("nan"), float("nan"))
    rate = successes / total
    denominator = 1 + z * z / total
    centre = (rate + z * z / (2 * total)) / denominator
    margin = z * sqrt(rate * (1 - rate) / total + z * z / (4 * total * total)) / denominator
    return centre - margin, centre + margin


def repeat_purchase_60d(invoices: pd.DataFrame, analysis_end: pd.Timestamp, window_days: int = 60) -> dict[str, float | int]:
    ordered = invoices.sort_values(["CustomerID", "invoice_date", "InvoiceNo"])
    first = ordered.groupby("CustomerID")["invoice_date"].min().rename("first_date")
    eligible = first[first <= analysis_end - pd.Timedelta(days=window_days)]
    merged = ordered.join(eligible, on="CustomerID", how="inner")
    later = merged[
        (merged["invoice_date"] > merged["first_date"])
        & (merged["invoice_date"] <= merged["first_date"] + pd.Timedelta(days=window_days))
    ]
    successes = int(later["CustomerID"].nunique())
    total = int(eligible.size)
    lower, upper = wilson_interval(successes, total)
    return {"successes": successes, "eligible_customers": total, "rate": successes / total if total else float("nan"), "ci_low": lower, "ci_high": upper}


def segment_customers(invoices: pd.DataFrame, config: AnalysisConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    history = invoices[invoices["invoice_date"] < config.snapshot_date].copy()
    snapshot = history.groupby("CustomerID").agg(
        last_purchase=("invoice_date", "max"),
        frequency=("InvoiceNo", "nunique"),
        monetary=("order_value", "sum"),
    )
    snapshot["recency_days"] = (config.snapshot_date - snapshot["last_purchase"]).dt.days
    freq_cut = float(snapshot["frequency"].quantile(config.segment_quantile))
    money_cut = float(snapshot["monetary"].quantile(config.segment_quantile))
    recent_cut = float(snapshot["recency_days"].quantile(1 - config.segment_quantile))
    lapsed_cut = float(snapshot["recency_days"].quantile(config.segment_quantile))

    def assign(row: pd.Series) -> str:
        if row["recency_days"] <= recent_cut and row["frequency"] >= freq_cut:
            return "frequent_recent"
        if row["recency_days"] <= recent_cut and row["frequency"] == 1:
            return "recent_first_time"
        if row["recency_days"] >= lapsed_cut and row["monetary"] >= money_cut:
            return "valuable_lapsed"
        return "other"

    snapshot["segment"] = snapshot.apply(assign, axis=1)
    followup_end = config.snapshot_date + pd.Timedelta(days=config.followup_days)
    followup = invoices[(invoices["invoice_date"] >= config.snapshot_date) & (invoices["invoice_date"] < followup_end)]
    repeaters = set(followup["CustomerID"])
    snapshot["purchased_in_followup"] = snapshot.index.isin(repeaters)
    outcomes = snapshot.groupby("segment").agg(customers=("segment", "size"), repeat_rate=("purchased_in_followup", "mean")).reset_index()
    thresholds = pd.DataFrame([{"frequency_cut": freq_cut, "money_cut": money_cut, "recent_cut_days": recent_cut, "lapsed_cut_days": lapsed_cut}])
    return snapshot.reset_index(), outcomes.merge(thresholds, how="cross")


def experiment_power_grid(
    baselines: tuple[float, ...] = (0.20, 0.35, 0.50),
    absolute_effects: tuple[float, ...] = (0.03, 0.05, 0.08),
    alpha: float = 0.05,
    power: float = 0.80,
) -> pd.DataFrame:
    """Approximate per-arm sample sizes for a two-sided two-proportion test."""
    z_alpha = NormalDist().inv_cdf(1 - alpha / 2)
    z_power = NormalDist().inv_cdf(power)
    rows = []
    for baseline in baselines:
        for effect in absolute_effects:
            treatment = baseline + effect
            pooled = (baseline + treatment) / 2
            numerator = (
                z_alpha * sqrt(2 * pooled * (1 - pooled))
                + z_power
                * sqrt(baseline * (1 - baseline) + treatment * (1 - treatment))
            ) ** 2
            per_arm = int(numerator / effect**2) + 1
            rows.append(
                {
                    "assumed_baseline": baseline,
                    "minimum_detectable_absolute_effect": effect,
                    "customers_per_arm": per_arm,
                    "total_customers": per_arm * 2,
                }
            )
    return pd.DataFrame(rows)
