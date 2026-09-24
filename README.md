# CartScope

CartScope is a reproducible customer-retention analysis for transaction data. It distinguishes invoice lines from orders, separates purchases and credits, handles incomplete observation windows, builds observed-entry cohorts, and freezes customer segments before measuring later behaviour.

The repository runs immediately with deterministic demo data. Pass the [UCI Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail) workbook to analyse the real dataset (CC BY 4.0; cite Chen, D. 2015).

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

The next portfolio-quality addition is a two-page findings and experiment memo based on the measured UCI results. Do not write an uplift claim before running an actual experiment.
