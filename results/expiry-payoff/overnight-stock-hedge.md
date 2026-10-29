# Overnight stock-hedge evaluation

## Finding

No repeatable profit after costs has been established. This historical
evaluation compares ten short SPY calls with one long SPXW call, each with a
100 multiplier, under overnight stock-hedge rules. The main table uses the
full-cross fill, 5% gross funding and 1 bp stock slippage. Values are mean
dollars per selected expiry.

| Period | Expiries | No hedge | 500 shares | 1,000 shares | Opening ITM rule |
|---|---:|---:|---:|---:|---:|
| 2019 | 9 | -827.24 | -792.27 | -757.30 | -610.75 |
| 2022 H2 | 63 | +96.47 | -190.13 | -476.73 | -136.85 |
| 2024 | 195 | -508.10 | -211.54 | +85.02 | -90.03 |
| 2025 partial | 127 | +191.97 | +43.21 | -105.54 | +653.39 |

The primary 500-share estimates are -$190.13 in 2022 H2 (95% interval
[-$591.85, $255.63]), -$211.54 in 2024 ([-$447.40, $10.25]) and +$43.21 in
2025 ([-$279.14, $356.71]). Each interval includes zero. The 2019 sample has
only nine expiries and is not included in this interval summary.

The 500- and 1,000-share rules are precommitted fixed long-stock hedges at the
modeled expiry close. The 500-share rule leaves residual exposure bounded by
plus or minus 500 shares. The opening rule buys 1,000 SPY shares at the modeled
expiry close only when that day's SPY open is at least the previously frozen
SPY strike plus $0.01; otherwise it buys zero. Its size uses neither the expiry
close nor the assignment outcome.

The opening ITM rule is positive in 2025, with a mean of +$653.39 and a 95%
interval of [$125.64, $1,274.85]. Its mean is -$136.85 in 2022 H2 (interval
[-$363.56, $96.43]) and -$90.03 in 2024 ([-$279.89, $99.65]). In 2025 its
median is -$10.08, and 48 of 127 expiries have nonzero residual stock. The
2025 mean includes +$777.20 per expiry from overnight stock-price movement.
That positive secondary case is part of the record; it does not make the
result repeatable across periods.

## Assignment-oracle diagnostic

This counterfactual assumes assignment outcomes when assigning stock cover.
That information is not available as an operational rule and does not give a
guaranteed upper bound.

| Period | Mean dollars per expiry |
|---|---:|
| 2019 | -$63.75 |
| 2022 H2 | -$85.27 |
| 2024 | -$71.93 |
| 2025 partial | -$90.96 |

These values use the same full-cross, 5% gross-funding and 1 bp slippage case.

## Evaluation record

The run covered 394 expiry pairs and 1,182 fill rows across the four periods.
It produced 70,920 cases, 720 summary rows and 432 uncertainty rows. Independent
validation checked 2,361,472 comparisons, found zero mismatches and reported a
maximum absolute error of 1.0913936421275139e-10.

Run identifiers:

- Evaluated source checkout: `db5d980c7abc344af02e8ae98fc426da92df433e`
- Overnight-hedge source SHA-256: `6cca6772325e7d55c8a85ef6a444681d2a54175e9ddfb10949dfdae6748337f3`
- Protocol SHA-256: `30eae811523310cb174fb0c8b244337031b00f0b16f479d954a495d531040731`
- Input-manifest SHA-256: `576d58194e467bfb2b3ab7ae7ea49cede871a21f276330a6fd1ab447f82484e5`
- Selection SHA-256: `8156d9030ca082af279f2fd3c99cfb445fa21237a09b1782abb0911b7d4ac8f7`
- Validation-index SHA-256: `42ba3e479450a58ff2becee67d66a6e865be4a4ff639388a63fe8847a9409f57`

## Costs and limits

The cost model charges $0.65 per option contract in the base case and $1.50 in
the stress case. For hedge quantity `q` and assignment quantity `1000A`, stock
fees are `rate × (|q| + |q - 1000A|)`, with a rate of $0.005 per share in base
and $0.01 in stress. Residual short-stock borrow is 3% in base and 10% in
stress. Hedge funding is 5% in base and 10% in stress for the calendar days
from expiry to cover. Stock slippage sensitivities are 0, 1 and 5 bp. Dividends
remain cash in the residual position. These results do not calculate
capital-based Sharpe or return on investment.

The 2025 period covers January through August, through the August 28 expiry.
The 15:59 option-quote timing caveat applies to the 2024 and 2025 OptionMetrics
periods. Legacy 2019 and 2022 clock conventions remain unresolved.

All reported 95% intervals are descriptive ISO year/week cluster bootstraps
with 10,000 draws, seed 20261030 and type-7 quantiles. Paired arms use shared
draw indices. No untouched or predictive holdout was used.

The historical inputs had already been inspected. The evaluation did not run a
0DTE delta strategy or option closeout. Its assignment threshold is a proxy,
and partial assignment is unobserved. Daily OHLC data were not used to execute
fills. The public historical rerun has not been run.
