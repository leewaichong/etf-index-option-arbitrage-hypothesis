# 2023 morning-hedge replication

**Finding:** no reliable after-cost edge is established. Across 196 selected
expiry pairs, the primary morning-price rule lost an average of $48.96 per
package after modeled costs. Its descriptive 95% interval includes zero. The
rule improved the mean by $75.58 against the no-stock-hedge control, but that
paired interval also includes zero.

Read the [full assessment and tables](../../reports/expiry-payoff/morning-hedge-assessment-20261030.md)
and [PDF](../../reports/expiry-payoff/morning-hedge-assessment-20261030.pdf).
The aggregate tables are also available as
[machine-readable JSON](morning-hedge-replication-2023-summary.json). The 2026-10-30
overnight-stock-hedge study remains a separate period comparison in the
[earlier result note](overnight-stock-hedge.md).

## Primary comparison

The table uses the full-cross option fill, base costs, 5% gross prefunding and
1 bp stock slippage. Each figure is mean dollars per selected expiry. The 95%
intervals describe the absolute net mean and the paired difference from the
no-stock-hedge control, respectively.

| 2023 arm | Net mean | Absolute 95% interval | Paired mean vs no hedge | Paired 95% interval |
|---|---:|---:|---:|---:|
| No stock hedge | -$124.54 | [-$320.93, $75.75] | $0.00 | [$0.00, $0.00] |
| Fixed 500 long SPY shares | -$89.95 | [-$222.96, $45.40] | +$34.59 | [-$124.66, $178.70] |
| Fixed 1,000 long SPY shares | -$55.35 | [-$267.47, $144.87] | +$69.19 | [-$249.33, $357.40] |
| Morning-price rule, 1,000 or zero shares | -$48.96 | [-$221.01, $117.67] | +$75.58 | [-$119.83, $273.89] |

For the primary rule, mean gross P&L was $58.43 and modeled costs were $107.39
per expiry. Its interval does not establish positive mean P&L. The fixed 500-share
hedge leaves a residual position of either +500 or -500 shares. The opening-price
rule left nonzero residual stock in 69 of 196 pairs.

An assignment-oracle diagnostic averaged -$91.44 per expiry in the same
full-cross, base-cost, 1 bp slippage case, with a descriptive 95% interval of
[-$114.53, -$70.07]. It uses future assignment information, so it is not an
operational strategy or a guaranteed upper bound.

The prior 2025 opening-price-rule result was +$653.39 over 127 expiries from
January through August. Its interval was
[$125.64, $1,274.85], while its median was -$10.08. That positive secondary
period is part of the evidence, but the rule averaged -$136.85 in 2022 H2 and
-$90.03 in 2024. In 2025 it left nonzero modeled residual positions in 48 of
127 expiries; the mean overnight stock-price contribution was +$777.20. These
separate historical periods do not provide paired inference across years.

## Design and limits

The position was 10 short SPY calls and one long SPXW call, with a 100 multiplier
for each option contract. The 2023 calendar contains 196 one-calendar-day-DTE
expiry pairs and 588 pair/fill rows: 196 each at midpoint, halfway-to-cross and
full-cross. The statistical denominator is 196 pairs. The morning rule buys
1,000 SPY shares at the modeled expiry close only when the expiry-day SPY open is at least
the previously frozen SPY strike plus $0.01. Otherwise it buys zero. The rule
uses neither the expiry close nor assignment to set its quantity. The stock
transaction is modeled at the expiry close using the morning-price quantity; it
is not an executable opening fill. SPXW settlement uses the actual PM settlement
input.

The base model charges $0.65 for each of 11 option contracts. Stock fees are
$0.005 per share for `q + |q - 1000A|`, where `q` is the hedge quantity and
`A` is the modeled assignment indicator. Residual short borrow is 3%; stock
hedge funding is 5% from expiry through cover calendar days. Stress assumptions
use $1.50 option fees, $0.01 stock fees per share, and 10% borrow and funding.
The analysis tests 0, 1 and 5 bp of stock slippage. Dividends remain cash in the
residual position. No capital-based Sharpe ratio or return on investment is
reported.

All 95% intervals are descriptive expiry ISO year/week cluster bootstraps with
10,000 draws, seed 20261030 and type-7 quantiles. Paired arms use shared draw
indices. Some 2023 option examples and 2019-2025 stock history had been inspected
earlier. The full 68,903-row quote export had not been inspected before the
protocol froze. This additional historical sample was not a globally untouched
or predictive holdout. The 2023 quote clock is unverified. This one-calendar-DTE study does
not test 0DTE delta hedging or option closeout. Assignment uses a threshold proxy,
partial assignment is unobserved, and daily OHLC data do not establish executable
fills, capacity or margin. Licensed inputs and private frozen controls are not
published. The public historical rerun is **NOT RUN**.

## Evaluation record

The evaluation produced 196 pairs and 588 pair/fill rows across the three fill
methods, yielding 35,280 cases in 180 scenario groups and 5,760 confidence
intervals. Independent validation checked
1,777,327 comparisons, found no mismatches and reported a maximum error of
`5.2523319027386606e-11`.

- Evaluated clean source checkout: `64e72887b782fdf838257a09877ffb817dfbfbdf`
- Exported adapter SHA-256: `02cd50de29e5c843a2bbace14ce1825d6027ea2268eec105878396a2030b8a13`
- Protocol SHA-256: `8f66787ce63d47771c1bbb5edd516c02d46ebc37b2538f3581ae3e073cbfa403`
- Input-manifest SHA-256: `47972793ea9daadfa35e5fa7aea884f61759d750525384946f18994dc1b89656`
- Selection SHA-256: `00cff4fb8c3ec13d9ea72cc4ee4d4c5cc1723747159bdea723305e2c6a167f13`
- Independent-validation receipt SHA-256: `4e297cb6a8c941c9dce33532c7355aad4d3ce0d39d30a105d42aeab1e4b0cba3`

The selected aggregate tables were copied byte-for-byte from the approved public
aggregate. Other cohort, confidence-interval and draw details remain in the
hashed private full summary. The published files exclude raw licensed inputs,
trade-level rows and private run paths.
