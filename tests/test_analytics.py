from pathlib import Path

import pandas as pd

from cartscope.analytics import (
    AnalysisConfig,
    cohort_retention,
    experiment_power_grid,
    prepare_lines,
    purchase_invoices,
    repeat_purchase_60d,
    segment_customers,
)
from cartscope.data import demo_transactions
from cartscope.sql_analysis import run_sql_reports


def test_invoice_lines_are_not_counted_as_orders() -> None:
    invoices = purchase_invoices(prepare_lines(demo_transactions()))
    purchase_lines = prepare_lines(demo_transactions()).query("line_status == 'purchase' and is_identified")
    assert len(invoices) < len(purchase_lines)


def test_anonymous_and_credit_rows_do_not_become_purchases() -> None:
    invoices = purchase_invoices(prepare_lines(demo_transactions()))
    assert invoices["CustomerID"].notna().all()
    assert not invoices["InvoiceNo"].str.startswith("C").any()


def test_repeat_purchase_excludes_incomplete_window() -> None:
    invoices = purchase_invoices(prepare_lines(demo_transactions()))
    result = repeat_purchase_60d(invoices, pd.Timestamp("2011-12-09"), 60)
    assert result["eligible_customers"] == 6
    assert 0 <= result["ci_low"] <= result["rate"] <= result["ci_high"] <= 1


def test_cohort_month_zero_is_complete() -> None:
    invoices = purchase_invoices(prepare_lines(demo_transactions()))
    cohorts = cohort_retention(invoices)
    month_zero = cohorts[cohorts["month_number"] == 0]
    assert (month_zero["retention_rate"] == 1).all()


def test_post_snapshot_orders_do_not_change_segment_features() -> None:
    invoices = purchase_invoices(prepare_lines(demo_transactions()))
    config = AnalysisConfig(pd.Timestamp("2011-12-09"), snapshot_date=pd.Timestamp("2011-10-01"))
    before, _ = segment_customers(invoices, config)
    extra = invoices.iloc[[0]].copy()
    extra["InvoiceNo"] = "LATE99"
    extra["invoice_date"] = pd.Timestamp("2011-10-15")
    after, _ = segment_customers(pd.concat([invoices, extra], ignore_index=True), config)
    cols = ["CustomerID", "frequency", "monetary", "recency_days", "segment"]
    pd.testing.assert_frame_equal(before[cols], after[cols])


def test_smaller_detectable_effect_requires_more_customers() -> None:
    grid = experiment_power_grid(baselines=(0.35,), absolute_effects=(0.03, 0.08))
    assert grid.iloc[0]["customers_per_arm"] > grid.iloc[1]["customers_per_arm"]


def test_visible_sql_reconciles_purchase_rows(tmp_path) -> None:
    lines = prepare_lines(demo_transactions())
    invoices = purchase_invoices(lines)
    reports = run_sql_reports(Path("sql"), tmp_path, lines, invoices)
    purchase = reports["line_reconciliation"].query("line_status == 'purchase'").iloc[0]
    assert int(purchase["rows"]) == int((lines["line_status"] == "purchase").sum())
