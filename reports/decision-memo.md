# Retention decision memo

**Decision owner:** Retention product manager  
**Evidence:** UCI Online Retail transactions, December 2010–December 2011  
**Decision:** Do not infer campaign uplift from the historical segment differences. Prepare a
customer-randomised reminder experiment only when the eligible population and guardrail data
meet the pre-declared launch conditions below.

## What the analysis establishes

CartScope reconciled 541,909 transaction lines into 18,532 qualifying purchase invoices.
Among 3,721 customers with a complete 60-day observation window, 1,393 purchased again:
**37.44%** (95% Wilson interval **35.89%–39.00%**).

At the 1 October 2011 snapshot, subsequent observed 60-day purchase rates differed by frozen
segment:

| Segment | Customers | Observed repeat rate |
|---|---:|---:|
| Frequent/recent | 462 | 79.87% |
| Other | 2,895 | 42.80% |
| Recent first-time | 217 | 38.71% |
| Valuable/lapsed | 42 | 38.10% |

These are descriptive associations. Selection into a segment reflects prior behaviour, and the
dataset has no marketing assignment, contact consent, margin or campaign-cost data. The table
does not estimate what would happen if any segment were contacted.

## Recommended action

Do not launch a valuable/lapsed-only test from this snapshot: 42 customers cannot support a
useful two-arm estimate. If a current, consented population can be assembled, test one relevant
reminder against business-as-usual at customer level. Avoid a discount in the first test so the
intervention measures reminder value without confounding it with price reduction.

The 2,895-customer `other` segment is an upper bound before contact-permission and operational
exclusions. At its observed 42.8% repeat rate, the approximate two-sided sample requirements are:

| Minimum detectable absolute lift | Customers per arm | Total customers | Feasible from 2,895? |
|---:|---:|---:|:---:|
| 3 percentage points | 4,303 | 8,606 | No |
| 5 percentage points | 1,555 | 3,110 | No |
| 8 percentage points | 610 | 1,220 | Potentially |

The existing snapshot is therefore slightly underpowered for a 5-point target even before
consent exclusions. Accumulate eligible customers over time, or decide explicitly that only an
8-point change would justify implementation. Do not weaken the minimum detectable effect after
seeing results.

## Pre-registered experiment

- **Unit and allocation:** customer, 50/50 persistent assignment.
- **Primary outcome:** at least one qualifying positive purchase invoice within 60 days.
- **Population:** every assigned eligible customer, analysed by original assignment.
- **Secondary outcomes:** gross purchase value and credit value per assigned customer.
- **Guardrails:** unsubscribe, complaint, credit and cancellation rates. Their thresholds require
  current operational baselines before launch.
- **Integrity check:** sample-ratio-mismatch test at 1%; investigate and invalidate the ship
  decision if it fails.
- **Decision rule:** ship only if the 95% absolute-lift interval excludes zero, observed lift is
  at least 5 percentage points and no approved guardrail limit is breached.

The machine-readable specification is in `configs/retention_experiment.yaml`; the executable
analysis is `cartscope-experiment`. The analyser rejects duplicate customers and malformed
outcomes, reports Wilson arm intervals and a Newcombe interval for the difference, and applies
the declared sample-ratio and primary-outcome gate. It reports that guardrail review is still
required rather than issuing a final ship decision without the operational data.

## Economics and missing information

An effect can be statistically positive and still lose money. Before launch, collect contribution
margin per incremental order, delivery/fulfilment cost, contact cost and any discount cost. The
break-even absolute lift is:

```text
(contact cost + expected incremental service/discount cost) / contribution margin per order
```

Use the economically relevant lift as the minimum effect in the final power calculation. The UCI
dataset can demonstrate the analytical workflow, but it cannot supply these current business
inputs or a causal campaign effect.
