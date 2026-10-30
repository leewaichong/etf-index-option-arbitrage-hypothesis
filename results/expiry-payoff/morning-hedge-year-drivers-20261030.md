# Morning-hedge year-driver attribution

The 2025 January-August mean net P&L was $653.39 across 127 observations, compared
with -$56.12 across 131 January-August 2023 observations. That $709.51 mean gap
is almost entirely an accounting difference in overnight stock contribution:
$706.14, or 99.5%. The 2025 result is positive on mean and negative on median
(-$10.08). This post-hoc attribution does not identify a predictive, causal or
tradable filter.

For the broader comparison, 2025 January-August versus all of 2023, the net mean
gap was $702.35; the overnight term contributed $694.25, or 98.8%. The primary
report gives the strategy setup and its wider limitations. See the existing
[archived eight-page morning-hedge report](../../reports/expiry-payoff/archive/morning-hedge-assessment-before-2024-comparison-20261030.md)
and [PDF](../../reports/expiry-payoff/archive/morning-hedge-assessment-before-2024-comparison-20261030.pdf).

## Cohort means

Dollars per package of 10 short SPY calls and one long SPXW call, with a 100
multiplier per contract. “Net minus overnight” removes only the overnight stock
price term while retaining modeled costs. It is an accounting diagnostic.

| Window | Observations | Mean net P&L | Median net P&L | Mean overnight stock term | Net minus overnight, modeled costs retained |
|---|---:|---:|---:|---:|---:|
| 2023 full year | 196 | -$48.96 | -$66.70 | +$82.96 | -$131.92 |
| 2023 January-August | 131 | -$56.12 | -$47.16 | +$71.07 | -$127.19 |
| 2025 January-August | 127 | +$653.39 | -$10.08 | +$777.20 | -$123.81 |

Both same-window diagnostics remain negative after retaining modeled costs. The 2025 cohort therefore
shows a positive total mean alongside a negative median, and it does not show
positive mean net P&L after removing the overnight price term.

## Nine-component mean bridge

The table decomposes the 2025 January-August mean minus the 2023 mean. The
full-year column compares 2025 January-August with 2023 full year; the matched
window column compares January-August in each year.

| Component | 2025 Jan-Aug minus 2023 full year | 2025 Jan-Aug minus 2023 Jan-Aug |
|---|---:|---:|
| Overnight stock term | +$694.25 | +$706.14 |
| Option baseline | +$26.93 | +$17.03 |
| Dividends | +$29.91 | +$37.87 |
| Hedge funding | -$27.71 | -$30.27 |
| Option fees | $0.00 | $0.00 |
| Premium-debit funding | $0.00 | $0.00 |
| Residual short borrow | +$0.24 | +$0.49 |
| Stock fees | -$0.51 | -$0.49 |
| Stock slippage | -$20.75 | -$21.25 |
| **Net mean difference** | **+$702.35** | **+$709.51** |

Independent ISO-week bootstrap 95% intervals for the net mean difference were
[$145.76, $1,356.61] for the full-year comparison and [$140.25, $1,378.36] for
the January-August comparison. These intervals are descriptive and do not
correct for post-hoc analysis.

## Residual-stock states

The residual state frequencies were similar in the matched windows. The change
in overnight contribution came mainly from conditional payoffs, especially the
2025 short-residual state, rather than a large frequency shift.

| Residual state | 2023 count (share) | 2023 weighted overnight contribution | 2025 count (share) | 2025 weighted overnight contribution | 2025 minus 2023 |
|---|---:|---:|---:|---:|---:|
| Flat | 82 (62.6%) | $0.00 | 79 (62.2%) | $0.00 | $0.00 |
| Long | 23 (17.6%) | +$79.54 | 27 (21.3%) | +$255.47 | +$175.93 |
| Short | 26 (19.8%) | -$8.47 | 21 (16.5%) | +$521.73 | +$530.21 |

Within the short-residual state, the conditional overnight payoff difference
contributed +$581.75 per package to the matched-window gap; the frequency
component offset it by $51.54. The observed 2025 contribution reflects favorable
stock declines while residual short stock was held. This accounting breakdown
does not show that the strategy caused those moves or that the state could be
selected in advance.

## Removing the largest winners

These are post-hoc fixed-count sensitivities in the 2025 January-August cohort,
which begins with 127 observations. The median remains negative after each
removal. The deletions are not trading rules.

| Largest net winners removed | Removed | Remaining | Mean net P&L | Median net P&L |
|---:|---:|---:|---:|---:|
| 1 | 1 | 126 | +$497.67 | -$17.54 |
| 5 | 5 | 122 | +$152.59 | -$27.15 |
| 10 | 10 | 117 | -$105.30 | -$44.71 |

## Method and limits

This is a post-hoc descriptive accounting attribution for the
`open_itm_q1000|full_cross|base|1bp|gross_prefunding` scenario. It compares the
full 2023 cohort and the common January-August window for 2023 and 2025. The
periods are not globally untouched or predictive holdouts. Historical stock
data and prior outcomes were inspected.

The evaluation used 10,000 independent ISO-week bootstrap draws for each year.
The full comparison used seed 20261030; the January-August comparison used seed
20261031. Quantiles use type-7 linear interpolation. The intervals are
uncorrected for post-hoc analysis.

The strategy is a one-calendar-day theoretical daily-close design. The option
quote clock is verified at 15:59 ET for 2024 and 2025; the 2023 quote clock
remains unverified. Stock and settlement references use later close values.
2025 covers January through August only. These figures do not
establish causality, predictiveness, execution at quoted prices, or a tradable
filter.

The approved summary includes selected aggregate tables only. It excludes raw
licensed quotes, individual trade rows and bootstrap draw arrays. The component
bridge is rounded to cents, so its displayed rows can differ from the displayed
total by one cent.

## Evaluation record

- Evaluated Git SHA: `9a7c219c6ef886929621fc3863cf51dca660a6d6`
- Evaluated source SHA-256: `36ec51840e6a5ff77ca9403e6557199963bd6b6ec40077bbdcfa965808e129cb`
- Input-manifest SHA-256: `1c6cc79b3746f00fa2c39c7f6d73f6798a6ee40bac404f1d9466c6b3d5aa2c3f`
- Protocol SHA-256: `e3fb30c4705e8e40511ca4007811ec742c97b346abcdfb0039844cee5f4ece39`
- Run-manifest SHA-256: `f029a778ee59fd27dafe37e561fc8f4a4e7a4a28f37f126dc920f3f340291a47`
- Independent-validation receipt SHA-256: `011edba0f0bd7949e78ac1662551945d1298d1b9f8a8b3ece5c048f7372558bf`
- Public aggregate summary SHA-256: `ac33f98ce67b3f955fb6d2a63958fa1bcc5404ccfed2a471f5271bddf13e06db`

Independent validation passed 2,189,579 comparisons with zero mismatches and
maximum error `8.585629984736443e-10`.
