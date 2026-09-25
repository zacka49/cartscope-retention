# CartScope

CartScope is a reproducible customer-retention analysis for transaction data. It distinguishes invoice lines from orders, separates purchases and credits, handles incomplete observation windows, builds observed-entry cohorts, and freezes customer segments before measuring later behaviour.

The repository runs immediately with deterministic demo data. Pass the [UCI Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail) workbook to analyse the real dataset (CC BY 4.0; cite Chen, D. 2015).

## Decision supported

The measured data describes repeat purchasing; it does not show that a retention campaign causes
uplift. The [decision memo](reports/decision-memo.md) therefore recommends against a 42-customer
valuable/lapsed test and specifies a customer-randomised reminder experiment with a fixed
5-percentage-point decision threshold, sample-ratio checks, uncertainty and operational
guardrails. At the observed 42.8% baseline, that target needs about **3,110 customers** in total,
slightly more than the 2,895-customer candidate segment before consent exclusions.

## Quick start

```powershell
uv sync --extra dev
uv run cartscope --output outputs/demo
uv run pytest
Start-Process outputs/demo/report.html
```

Real data:

```powershell
uv run cartscope --input "data/raw/Online Retail.xlsx" --output outputs/uci
```

Outputs include a cleaning ledger, visible DuckDB SQL reports, cohort table, 60-day repeat-purchase estimate with a Wilson interval, frozen customer segments, later segment outcomes, an experiment power grid, a machine-readable manifest, and a standalone HTML report.

The optional [incremental pipeline](docs/incremental-pipeline.md) adds append-only source versions, idempotent replay, corrections, late credits, tombstones and a tested incremental-versus-full-rebuild reconciliation. It requires a real source event key rather than pretending that all identical retail rows are duplicates.

Analyse a completed customer-randomised experiment from a CSV containing `customer_id`,
`variant` and `purchased_60d`:

```powershell
uv run cartscope-experiment --input data/experiment_assignments.csv --output outputs/experiment/result.json
```

The analysis follows the versioned [experiment specification](configs/retention_experiment.yaml),
checks sample-ratio mismatch, reports arm and absolute-lift intervals, and applies the pre-declared
primary-outcome gate. A final ship decision still requires the separately approved operational
guardrails. The analysis uses intent to treat: each customer must appear exactly once under their
original assignment.

## Measured UCI run

The verified real-data run processed 541,909 rows into 18,532 qualifying purchase invoices. Of 3,721 customers with a complete 60-day follow-up window, 1,393 purchased again: **37.44%** with a 95% Wilson interval of **35.89%–39.00%**. See [the measured summary](reports/uci-summary.md) for reconciliation, segment outcomes and limitations.

## Analytical contract

- A purchase is a positive-quantity, positive-price line on a non-cancellation invoice.
- Order frequency counts distinct invoices, not rows.
- Anonymous transactions are visible in reconciliation but excluded from customer denominators.
- A 60-day repeat rate only includes customers with a complete 60-day observation window.
- Segments are frozen on 1 October 2011; later purchases only affect the outcome.
- Results are observational and historical. They do not establish a treatment effect, profit, or current customer behaviour.

## Repository layout

```text
src/cartscope/       data loading, contracts, analysis, reporting, CLI
sql/                  executable reconciliation, country and monthly queries
configs/             versioned analysis choices
tests/               invoice, censoring, cohort and leakage checks
outputs/             generated and ignored by Git
```

The repository deliberately stops short of an uplift claim. A causal estimate requires a real
randomised assignment and current operational guardrail data.
