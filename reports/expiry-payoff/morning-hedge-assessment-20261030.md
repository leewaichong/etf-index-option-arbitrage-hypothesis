# SPY/SPX morning hedge: three-year comparison

## Executive summary

**January-August 2025 was the positive exception among the three historical samples. The same fixed morning hedge lost money after modeled costs in 2023 and 2024, including their January-August windows. A repeatable after-cost edge remains unproven.**

- On the common January-August window, mean net P&L per package was -$56.12 in 2023 across 131 pairs, -$146.26 in 2024 across 131 pairs, and +$653.39 in 2025 across 127 pairs.
- Full-year 2024 averaged -$90.03 after modeled costs, with a -$57.16 median and 39.0% positive packages. The hedge improved the mean by $418.07 versus no hedge, which averaged -$508.10.
- Average overnight stock contribution was -$1.90 in full-year 2024 versus +$777.20 in January-August 2025. Favorable overnight moves explain the positive 2025 result; its average modeled costs were higher.
- Removing the ten largest 2025 winners leaves 117 observations with a -$105.30 mean. The original 2025 median was -$10.08. This is a post-hoc sensitivity, not a trading filter.

## Cohort results

Focal case: full-cross fills, base costs, gross prefunding, 1 bp stock slippage. The original formal primary arm was fixed-500; this morning arm was secondary.

| Cohort | n | Mean USD/expiry | Median USD/expiry | Total USD | Positive | Gross total USD | Costs total USD | Overnight total USD | Dividends total USD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Full 2023 | 196 | -$48.96 | -$66.70 | -$9,596.60 | 40.3% | $11,452.43 | $21,049.03 | $16,260.00 | -$3,144.57 |
| Full 2024 | 195 | -$90.03 | -$57.16 | -$17,555.09 | 39.0% | $9,236.94 | $26,792.03 | -$370.00 | $1,594.94 |
| Jan-Aug 2025 | 127 | $653.39 | -$10.08 | $82,980.62 | 48.0% | $102,809.12 | $19,828.50 | $98,705.00 | $1,761.12 |
| Jan-Aug 2023 | 131 | -$56.12 | -$47.16 | -$7,351.92 | 41.2% | $6,351.43 | $13,703.35 | $9,310.00 | -$3,144.57 |
| Jan-Aug 2024 | 131 | -$146.26 | -$65.13 | -$19,160.49 | 38.2% | -$1,190.06 | $17,970.43 | -$8,380.00 | $1,594.94 |

## Components and states

| Cohort | Option baseline total | q0 control mean | Overnight total | Dividends total | q=0 | q=1,000 | Assigned | Residual long / short / zero | Net P&L minus overnight contribution, retaining modeled costs (total USD) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Full 2023 | -$1,663.00 | -$124.54 | $16,260.00 | -$3,144.57 | 95 | 101 | 104 | 33 / 36 / 127 | -$25,856.60 |
| Full 2024 | $8,012.00 | -$508.10 | -$370.00 | $1,594.94 | 77 | 118 | 114 | 27 / 23 / 145 | -$17,185.09 |
| Jan-Aug 2025 | $2,343.00 | $191.97 | $98,705.00 | $1,761.12 | 52 | 75 | 69 | 27 / 21 / 79 | -$15,724.38 |
| Jan-Aug 2023 | $186.00 | -$58.50 | $9,310.00 | -$3,144.57 | 66 | 65 | 68 | 23 / 26 / 82 | -$16,661.92 |
| Jan-Aug 2024 | $5,595.00 | -$505.49 | -$8,380.00 | $1,594.94 | 50 | 81 | 78 | 20 / 17 / 94 | -$10,780.49 |

*Component columns are cohort totals in USD; q0 control is a per-expiry mean. The net-minus-overnight value is a total-dollar diagnostic, not a tradable return.*

Six modeled costs (total USD by cohort):

| Cohort | Option fees | Stock fees | Borrow | Premium funding | Hedge funding | Slippage |
|---|---:|---:|---:|---:|---:|---:|
| Full 2023 | $1,401.40 | $850.00 | $2,102.06 | $1.96 | $9,414.52 | $7,279.09 |
| Full 2024 | $1,394.25 | $840.00 | $1,628.99 | $3.34 | $13,836.20 | $9,089.25 |
| Jan-Aug 2025 | $908.05 | $615.00 | $1,331.59 | $1.65 | $9,619.94 | $7,352.28 |
| Jan-Aug 2023 | $936.65 | $570.00 | $1,438.33 | $1.28 | $5,957.15 | $4,799.94 |
| Jan-Aug 2024 | $936.65 | $590.00 | $1,146.63 | $1.93 | $9,121.29 | $6,173.93 |

## Source-cohort uncertainty and tail checks

Source-provided 95% type-7 intervals are shown for 2023 full year, 2024 full year, and 2025 Jan-Aug. These are previously inspected historical samples, not holdouts or predictive validation. The filtered Jan-Aug 2023 and Jan-Aug 2024 cohorts have no computed intervals. No new or common-window intervals were computed.

| Source cohort | Hedge mean, absolute 95% CI | Paired vs q0 mean, 95% CI |
|---|---:|---:|
| 2023 full year | -$48.96 [-$221.01, $117.67], n=196 | $75.58 [-$119.83, $273.89], n=196 |
| 2024 full year | -$90.03 [-$279.89, $99.65], n=195 | $418.07 [$132.92, $714.32], n=195 |
| 2025 Jan-Aug | $653.39 [$125.64, $1,274.85], n=127 | $461.42 [-$90.96, $1,063.93], n=127 |

Tail-removal means are USD per package after removing the largest or smallest k net outcomes. n after 10 is the count left after removing 10 outcomes. This is a post-hoc sensitivity check, not a trading filter.

| Cohort | Remove top 1 mean | Remove top 5 mean | Remove top 10 mean | Remove bottom 1 mean | Remove bottom 5 mean | Remove bottom 10 mean | n after 10 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Full 2023 | -$74.66 | -$143.47 | -$218.13 | -$27.90 | $43.58 | $122.34 | 186 |
| Full 2024 | -$138.85 | -$245.66 | -$327.82 | -$52.86 | $60.80 | $157.81 | 185 |
| Jan-Aug 2025 | $497.67 | $152.59 | -$105.30 | $736.85 | $981.57 | $1,117.78 | 117 |
| Jan-Aug 2023 | -$94.73 | -$195.90 | -$306.04 | -$24.58 | $79.13 | $181.65 | 121 |
| Jan-Aug 2024 | -$200.08 | -$324.69 | -$401.54 | -$91.24 | $78.94 | $180.56 | 121 |

## Monthly net results

| Month | 2023 n / mean | 2024 n / mean | 2025 n / mean |
|---|---:|---:|---:|
| 01 | 15 / -$317.49 | 16 / -$0.20 | 14 / -$107.17 |
| 02 | 15 / $207.01 | 16 / -$470.75 | 15 / $816.54 |
| 03 | 19 / -$291.41 | 16 / -$462.13 | 16 / $859.12 |
| 04 | 15 / $660.30 | 17 / -$356.23 | 17 / $1,017.19 |
| 05 | 17 / -$165.66 | 18 / -$8.87 | 17 / $1,612.49 |
| 06 | 17 / -$424.32 | 14 / -$550.27 | 14 / $784.83 |
| 07 | 14 / -$131.94 | 16 / $626.51 | 18 / $171.21 |
| 08 | 19 / $95.49 | 18 / -$18.66 | 16 / -$17.94 |
| 09 | 16 / -$856.56 | 15 / $602.48 | 0 / n/a |
| 10 | 17 / $542.12 | 19 / -$251.43 | 0 / n/a |
| 11 | 16 / $11.85 | 15 / -$572.48 | 0 / n/a |
| 12 | 16 / $128.42 | 15 / $395.51 | 0 / n/a |

## Cost sensitivity

36 source cases per year. Means are net dollars per expiry.

| Year | Fill | Costs | Slippage | Funding | n | Mean |
|---|---|---|---:|---|---:|---:|
| 2024 | full_cross | base | 0.0 bp | assignment_cash_net | 195 | $13.54 |
| 2024 | full_cross | base | 0.0 bp | gross_prefunding | 195 | -$43.41 |
| 2024 | full_cross | base | 1.0 bp | assignment_cash_net | 195 | -$33.08 |
| 2024 | full_cross | base | 1.0 bp | gross_prefunding | 195 | -$90.03 |
| 2024 | full_cross | base | 5.0 bp | assignment_cash_net | 195 | -$219.52 |
| 2024 | full_cross | base | 5.0 bp | gross_prefunding | 195 | -$276.47 |
| 2024 | full_cross | stress | 0.0 bp | assignment_cash_net | 195 | -$33.64 |
| 2024 | full_cross | stress | 0.0 bp | gross_prefunding | 195 | -$147.54 |
| 2024 | full_cross | stress | 1.0 bp | assignment_cash_net | 195 | -$80.25 |
| 2024 | full_cross | stress | 1.0 bp | gross_prefunding | 195 | -$194.15 |
| 2024 | full_cross | stress | 5.0 bp | assignment_cash_net | 195 | -$266.69 |
| 2024 | full_cross | stress | 5.0 bp | gross_prefunding | 195 | -$380.59 |
| 2024 | halfway | base | 0.0 bp | assignment_cash_net | 195 | $23.84 |
| 2024 | halfway | base | 0.0 bp | gross_prefunding | 195 | -$33.11 |
| 2024 | halfway | base | 1.0 bp | assignment_cash_net | 195 | -$22.77 |
| 2024 | halfway | base | 1.0 bp | gross_prefunding | 195 | -$79.72 |
| 2024 | halfway | base | 5.0 bp | assignment_cash_net | 195 | -$209.21 |
| 2024 | halfway | base | 5.0 bp | gross_prefunding | 195 | -$266.16 |
| 2024 | halfway | stress | 0.0 bp | assignment_cash_net | 195 | -$23.33 |
| 2024 | halfway | stress | 0.0 bp | gross_prefunding | 195 | -$137.23 |
| 2024 | halfway | stress | 1.0 bp | assignment_cash_net | 195 | -$69.94 |
| 2024 | halfway | stress | 1.0 bp | gross_prefunding | 195 | -$183.84 |
| 2024 | halfway | stress | 5.0 bp | assignment_cash_net | 195 | -$256.38 |
| 2024 | halfway | stress | 5.0 bp | gross_prefunding | 195 | -$370.28 |
| 2024 | midpoint | base | 0.0 bp | assignment_cash_net | 195 | $34.15 |
| 2024 | midpoint | base | 0.0 bp | gross_prefunding | 195 | -$22.80 |
| 2024 | midpoint | base | 1.0 bp | assignment_cash_net | 195 | -$12.46 |
| 2024 | midpoint | base | 1.0 bp | gross_prefunding | 195 | -$69.41 |
| 2024 | midpoint | base | 5.0 bp | assignment_cash_net | 195 | -$198.90 |
| 2024 | midpoint | base | 5.0 bp | gross_prefunding | 195 | -$255.85 |
| 2024 | midpoint | stress | 0.0 bp | assignment_cash_net | 195 | -$13.02 |
| 2024 | midpoint | stress | 0.0 bp | gross_prefunding | 195 | -$126.92 |
| 2024 | midpoint | stress | 1.0 bp | assignment_cash_net | 195 | -$59.63 |
| 2024 | midpoint | stress | 1.0 bp | gross_prefunding | 195 | -$173.53 |
| 2024 | midpoint | stress | 5.0 bp | assignment_cash_net | 195 | -$246.07 |
| 2024 | midpoint | stress | 5.0 bp | gross_prefunding | 195 | -$359.97 |
| 2025 | full_cross | base | 0.0 bp | assignment_cash_net | 127 | $760.59 |
| 2025 | full_cross | base | 0.0 bp | gross_prefunding | 127 | $711.28 |
| 2025 | full_cross | base | 1.0 bp | assignment_cash_net | 127 | $702.70 |
| 2025 | full_cross | base | 1.0 bp | gross_prefunding | 127 | $653.39 |
| 2025 | full_cross | base | 5.0 bp | assignment_cash_net | 127 | $471.13 |
| 2025 | full_cross | base | 5.0 bp | gross_prefunding | 127 | $421.82 |
| 2025 | full_cross | stress | 0.0 bp | assignment_cash_net | 127 | $695.48 |
| 2025 | full_cross | stress | 0.0 bp | gross_prefunding | 127 | $596.86 |
| 2025 | full_cross | stress | 1.0 bp | assignment_cash_net | 127 | $637.58 |
| 2025 | full_cross | stress | 1.0 bp | gross_prefunding | 127 | $538.97 |
| 2025 | full_cross | stress | 5.0 bp | assignment_cash_net | 127 | $406.02 |
| 2025 | full_cross | stress | 5.0 bp | gross_prefunding | 127 | $307.41 |
| 2025 | halfway | base | 0.0 bp | assignment_cash_net | 127 | $772.89 |
| 2025 | halfway | base | 0.0 bp | gross_prefunding | 127 | $723.59 |
| 2025 | halfway | base | 1.0 bp | assignment_cash_net | 127 | $715.00 |
| 2025 | halfway | base | 1.0 bp | gross_prefunding | 127 | $665.69 |
| 2025 | halfway | base | 5.0 bp | assignment_cash_net | 127 | $483.43 |
| 2025 | halfway | base | 5.0 bp | gross_prefunding | 127 | $434.13 |
| 2025 | halfway | stress | 0.0 bp | assignment_cash_net | 127 | $707.78 |
| 2025 | halfway | stress | 0.0 bp | gross_prefunding | 127 | $609.17 |
| 2025 | halfway | stress | 1.0 bp | assignment_cash_net | 127 | $649.89 |
| 2025 | halfway | stress | 1.0 bp | gross_prefunding | 127 | $551.28 |
| 2025 | halfway | stress | 5.0 bp | assignment_cash_net | 127 | $418.32 |
| 2025 | halfway | stress | 5.0 bp | gross_prefunding | 127 | $319.71 |
| 2025 | midpoint | base | 0.0 bp | assignment_cash_net | 127 | $785.20 |
| 2025 | midpoint | base | 0.0 bp | gross_prefunding | 127 | $735.89 |
| 2025 | midpoint | base | 1.0 bp | assignment_cash_net | 127 | $727.30 |
| 2025 | midpoint | base | 1.0 bp | gross_prefunding | 127 | $678.00 |
| 2025 | midpoint | base | 5.0 bp | assignment_cash_net | 127 | $495.74 |
| 2025 | midpoint | base | 5.0 bp | gross_prefunding | 127 | $446.43 |
| 2025 | midpoint | stress | 0.0 bp | assignment_cash_net | 127 | $720.09 |
| 2025 | midpoint | stress | 0.0 bp | gross_prefunding | 127 | $621.48 |
| 2025 | midpoint | stress | 1.0 bp | assignment_cash_net | 127 | $662.19 |
| 2025 | midpoint | stress | 1.0 bp | gross_prefunding | 127 | $563.58 |
| 2025 | midpoint | stress | 5.0 bp | assignment_cash_net | 127 | $430.63 |
| 2025 | midpoint | stress | 5.0 bp | gross_prefunding | 127 | $332.02 |

## Method and provenance

Expiry morning SPY open selects quantity using the frozen selected strike + $0.01 rule, with 1e-10 tolerance. The modeled stock purchase occurs at expiry close; the residual closes at the next session open. Options use one-calendar-day DTE from entry close to expiry close. The stock holding can span weekends. The option structure is 10 short SPY options and one long SPXW option, multiplier 100.

The original fixed-500 arm was the formal primary arm; this morning arm was secondary. These are previously inspected historical samples, not holdouts or predictive validation. The 2024 cohort covers expiries 2024-01-03 through 2024-12-31, with the final next-session cover open on 2025-01-02. The 2023 15:59 quote clock is unverified; it is verified for 2024 and 2025. Later closing references carry execution limits. Results use daily theoretical fills and do not establish operational edge. No common-window CIs or between-year p-values were computed.

Comparison builder Git SHA: `1ce2763318f930f793da29293f6b5df482ef3b42`. Comparison builder file SHA-256: `c154660c93f5faa269742428d516cf0cd544232147eaa7a7af390a4363ce1047`. Source evaluator Git SHAs: 2023 `64e72887b782fdf838257a09877ffb817dfbfbdf`, 2024/2025 `44ed294deddb85df594ad1e1c8a5a91bb22d08d7`.
Aggregate SHA-256: `aa4887efd7e11f2478cb361b5ec0af37c863c324581cee2c4e3f17ff1f58aff6`. Comparison run receipt SHA-256: `f2bc5ec4f7882e0c4339384d82ed4943852a5ee4d8be2e481a3167df032b8004`. Validation receipt SHA-256: `4d1b55c5c2010a066a86bec07fa14402033145ff36c80bbfeba00a5c0c753876`. Independent checker SHA-256: `b2ec4d5000533c1c492a7453a1c9c7563c619cf3c7dff73099930fc0ceb7ad83`.
Input manifest SHA-256: `dac4f37eb6f1685308067cbffbca0b91a46ea79d286935e6f1874b61c5f36aa5`. Protocol SHA-256: `207577186b5c0c9c078dcc3f203fefa86558a793fe4cb3d5aa96838187c76642`.

Source hashes:
- `attribution_manifest_2023`: `f029a778ee59fd27dafe37e561fc8f4a4e7a4a28f37f126dc920f3f340291a47`
- `case_ledgers_2024_2025`: `17a11c5cb21fcf00109a5f9b80f16aca8dc5be104f0d8c16e37daae2f8bcf638`
- `evaluator_manifest_2023`: `99d2b5fd64a6180a71e5e0513e2e58b4b4199ccc707ebaeb6eb802b99ae099c7`
- `evaluator_manifest_2024_2025`: `fbb9e214d3bca4323dbad44f17c9c5b09403f875db53c60db1af713a32713628`
- `execution_2023`: `3b50a9eea10ee0574f9fb2f6162ff491463503c50107415448d34a9865cc766a`
- `execution_2024_2025`: `ad559ec7f5b508025da6666b94b5cb80e0e23aaba7bd98ff92ae56d8f86caaf1`
- `ledger_2023`: `f413ad27f84407a28f152b1339d2cd5ba93de7057fddc3001d38494cf1161e04`
- `summaries_2024_2025`: `29a68896ee23d5cf02237ca089bc7725765877d135130a4040486bf0f9dbf02b`
- `summary_2023`: `22f712dbd9b63483035b3907f884848cc9bdadb6992dca1fec24333215113404`
- `uncertainty_2024_2025`: `b9b43b4978d8fa8ddd3ca5527caa64318f8be1f7e131ae056d5221e361271442`
- `validated_rows_2023`: `ba6728adaa6e00c95ded3b9477624827d269332f50c483050a09a356f6036f9e`
- `validation_2023`: `011edba0f0bd7949e78ac1662551945d1298d1b9f8a8b3ece5c048f7372558bf`
