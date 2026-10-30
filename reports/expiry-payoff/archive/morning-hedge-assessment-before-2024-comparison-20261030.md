# Morning SPY hedge assessment

Report date: 2026-10-30

## Verdict

The 2025 profit came mainly from favorable moves in the stock left overnight. The morning-price rule remains unproven as a repeatable strategy after costs.
The 2023 replication loses money, including over the same January-August window. All estimates retain the frozen theoretical daily-close design.

## Why the years differed
The overnight stock-price term explains 98.8% of the $702.35 mean P&L gap. Residual short-stock positions contribute most, benefiting from larger overnight declines in 2025.
The same January-August window still loses in 2023. Removing 2025's ten best trades turns its mean negative; removing five leaves a smaller profit.
With the overnight price term removed and retained modeled costs held fixed, both years lose. This accounting check does not model a risk-free hedge.

USD per package of ten short SPY option contracts and one long SPXW option contract. Figures are dollar P&L, not rates or annualized returns. Primary comparison uses full-cross, base costs, gross prefunding, and 1 bp stock slippage.

## Main comparison

| Period | n | Mean | Median | Total | 95% CI | Win rate |
|---|---|---|---|---|---|---|
| 2023 calendar year | 196 | -$48.96 | -$66.70 | -$9,596.60 | [-$221.01, $117.67] | 40.3% |
| 2025 Jan-Aug | 127 | $653.39 | -$10.08 | $82,980.62 | [$125.64, $1,274.85] | 48.0% |

## 2023 source coverage

| Coverage check | Count |
|---|---|
| Expected pairs | 196 |
| Complete pairs | 196 |
| Pair/fill rows | 588 |
| Scenario cases | 35280 |
| Actual returned quote rows | 68903 |
| Projection fields matched | 29 |

The statistical denominator is 196 pairs. The 588 pair/fill rows represent three hypothetical fill variants per pair, not 588 independent quote samples. The 35,280 scenario cases apply scenario combinations to those rows.

The 2023 replication is an additional historical sample, not a globally untouched or predictive holdout. The 2025 comparison covers January through August only, not a full year, and is not a paired inference against 2023.

## 2023 primary arms
All five arms use the same 196-pair sample. Absolute intervals measure each arm; paired intervals compare each arm with q0 on the shared sample.

| Arm | n | Mean | Median | Absolute 95% CI | Paired vs q0 95% CI | Win rate |
|---|---|---|---|---|---|---|
| q0 | 196 | -$124.54 | -$17.15 | [-$320.93, $75.75] | [$0.00, $0.00] | 47.4% |
| fixed 500 | 196 | -$89.95 | -$150.68 | [-$222.96, $45.40] | [-$124.66, $178.70] | 44.4% |
| fixed 1,000 | 196 | -$55.35 | -$137.01 | [-$267.47, $144.87] | [-$249.33, $357.40] | 33.2% |
| morning-price rule | 196 | -$48.96 | -$66.70 | [-$221.01, $117.67] | [-$119.83, $273.89] | 40.3% |
| assignment oracle | 196 | -$91.44 | -$77.16 | [-$114.53, -$70.07] | [-$164.47, $227.95] | 32.7% |

## Attribution: cohort comparison
2023 full year and January-August use different windows. The January-August comparison holds the calendar window constant. These are historical comparisons, not a predictive holdout.

| Cohort | n | Mean USD | Median USD | Total USD | Win rate | Min expiry | Max expiry |
|---|---|---|---|---|---|---|---|
| 2023 full year | 196 | -$48.96 | -$66.70 | -$9,596.60 | 40.3% | 2023-01-04 | 2023-12-29 |
| 2023 Jan-Aug | 131 | -$56.12 | -$47.16 | -$7,351.92 | 41.2% | 2023-01-04 | 2023-08-31 |
| 2025 Jan-Aug | 127 | $653.39 | -$10.08 | $82,980.62 | 48.0% | 2025-01-03 | 2025-08-28 |

Mean contribution diagnostics, USD per package.

| Cohort | Overnight mean | Option baseline | Dividend | Mean costs | Net excluding overnight | Winsorized 5-95 mean |
|---|---|---|---|---|---|---|
| 2023 full year | $82.96 | -$8.48 | -$16.04 | $107.39 | -$131.92 | -$40.24 |
| 2023 Jan-Aug | $71.07 | $1.42 | -$24.00 | $104.61 | -$127.19 | -$48.99 |
| 2025 Jan-Aug | $777.20 | $18.45 | $13.87 | $156.13 | -$123.81 | $604.60 |

Additive mean-P&L bridge, USD per package. Confidence intervals describe component differences. Costs appear as negative contributions.

| Component | 2023 mean | 2025 mean | Difference | 95% CI low | 95% CI high |
|---|---|---|---|---|---|
| Option baseline | -$8.48 | $18.45 | $26.93 | -$103.72 | $116.26 |
| Overnight stock contribution | $82.96 | $777.20 | $694.25 | $150.03 | $1,329.92 |
| Dividend cash | -$16.04 | $13.87 | $29.91 | $0.00 | $70.81 |
| Option fees (negative) | -$7.15 | -$7.15 | $0.00 | $0.00 | $0.00 |
| Stock fees (negative) | -$4.34 | -$4.84 | -$0.51 | -$1.24 | $0.22 |
| Short borrow (negative) | -$10.72 | -$10.48 | $0.24 | -$5.83 | $5.86 |
| Premium debit funding (negative) | -$0.01 | -$0.01 | $0.00 | -$0.01 | $0.00 |
| Hedge funding (negative) | -$48.03 | -$75.75 | -$27.71 | -$44.48 | -$11.15 |
| Stock slippage (negative) | -$37.14 | -$57.89 | -$20.75 | -$29.16 | -$12.19 |

Net excluding overnight keeps retained modeled costs fixed as an accounting diagnostic. It does not model a risk-free hedge strategy. A favorable overnight stock contribution is cash flow attribution, not evidence that the rule predicts or causes profit.

## Attribution: residual and tail checks
Residual frequency and payoff effects use a symmetric decomposition. Tail rows remove fixed counts from each cohort separately; they are post-hoc checks, not tradable filters. Winsorized means are standalone summaries and do not add across components.

All dollar amounts are USD per package. Year labels refer to 2023 and 2025. p is the cohort share. Conditional values are mean overnight contributions per residual state; all-cohort values are weighted overnight contributions.

| State | n '23 | n '25 | p '23 | p '25 | Cond. '23 | Cond. '25 | All '23 | All '25 | Frequency | Payoff |
|---|---|---|---|---|---|---|---|---|---|---|
| short | 36 | 21 | 18.37% | 16.54% | -$15.83 | $3,155.24 | -$2.91 | $521.73 | -$28.76 | $553.40 |
| flat | 127 | 79 | 64.80% | 62.20% | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 | $0.00 |
| long | 33 | 27 | 16.84% | 21.26% | $510.00 | $1,201.67 | $85.87 | $255.47 | $37.85 | $131.75 |

Tail removal uses fixed counts. Original denominators remain 196 for 2023 and 127 for 2025.

| Case | n 2023 after | mean 2023 after | removed sum 2023 | n 2025 after | mean 2025 after | removed sum 2025 |
|---|---|---|---|---|---|---|
| Remove best 1 | 195 | -$74.66 | $4,962.95 | 126 | $497.67 | $20,273.94 |
| Remove worst 1 | 195 | -$27.90 | -$4,156.44 | 126 | $736.85 | -$9,862.21 |
| Remove best 5 | 191 | -$143.47 | $17,805.39 | 122 | $152.59 | $64,364.26 |
| Remove worst 5 | 191 | $43.58 | -$17,920.47 | 122 | $981.57 | -$36,771.22 |
| Remove best 10 | 186 | -$218.13 | $30,975.94 | 117 | -$105.30 | $95,300.95 |
| Remove worst 10 | 186 | $122.34 | -$32,351.80 | 117 | $1,117.78 | -$47,799.29 |

Common January-August monthly comparison, USD per package.

| Month | n 2023 | mean 2023 | total 2023 | n 2025 | mean 2025 | total 2025 |
|---|---|---|---|---|---|---|
| 01 | 15 | -$317.49 | -$4,762.35 | 14 | -$107.17 | -$1,500.41 |
| 02 | 15 | $207.01 | $3,105.16 | 15 | $816.54 | $12,248.17 |
| 03 | 19 | -$291.41 | -$5,536.82 | 16 | $859.12 | $13,745.88 |
| 04 | 15 | $660.30 | $9,904.54 | 17 | $1,017.19 | $17,292.28 |
| 05 | 17 | -$165.66 | -$2,816.28 | 17 | $1,612.49 | $27,412.35 |
| 06 | 17 | -$424.32 | -$7,213.46 | 14 | $784.83 | $10,987.58 |
| 07 | 14 | -$131.94 | -$1,847.10 | 18 | $171.21 | $3,081.85 |
| 08 | 19 | $95.49 | $1,814.38 | 16 | -$17.94 | -$287.09 |

Return scales

| Year | Mean expiry SPY close, USD | Mean absolute overnight return, % | Mean signed overnight return, % |
|---|---|---|---|
| 2023 | $427.22 | 0.389% | 0.031% |
| 2025 | $593.56 | 0.573% | -0.037% |

Year-gap intervals are unpaired descriptive intervals, not paired year inference.

| Window | 95% CI low | 95% CI high |
|---|---|---|
| 2023 full year vs 2025 Jan-Aug | $145.76 | $1,356.61 |
| Both Jan-Aug | $140.25 | $1,378.36 |

## Driver findings

The overnight stock-price term explains 98.8% of the $702.35 mean P&L gap. Residual short-stock positions contribute most, benefiting from larger overnight declines in 2025.
The same January-August window still loses in 2023. Removing 2025's ten best trades turns its mean negative; removing five leaves a smaller profit.
With the overnight price term removed and retained modeled costs held fixed, both years lose. This accounting check does not model a risk-free hedge.

## Attribution provenance
Attribution intervals are uncorrected, post-hoc 95% descriptive intervals from 10,000 independent-year ISO expiry-week cluster resamples. The full-window comparison uses seed 20261030 and the January-August comparison seed 20261031. Each draw uses sampled row-sum totals divided by sampled row counts, with type-7 quantiles. They are unpaired and do not establish predictive or causal effects.
Attribution run SHA 9a7c219c6ef886929621fc3863cf51dca660a6d6, clean=True, started 2026-10-30T05:29:00.099609+00:00, ended 2026-10-30T05:29:02.697712+00:00. The report's original 2023 evaluation SHA remains 64e72887b782fdf838257a09877ffb817dfbfbdf; the 2025 source evaluation SHA is db5d980c7abc344af02e8ae98fc426da92df433e.
Attribution command (local paths redacted): [local path] -m spyspx.morning_hedge_attribution evaluate --input-manifest [local path] --input-manifest-sha256 1c6cc79b3746f00fa2c39c7f6d73f6798a6ee40bac404f1d9466c6b3d5aa2c3f --protocol [local path] --protocol-sha256 e3fb30c4705e8e40511ca4007811ec742c97b346abcdfb0039844cee5f4ece39 --out [local path]. Input manifest SHA-256 1c6cc79b3746f00fa2c39c7f6d73f6798a6ee40bac404f1d9466c6b3d5aa2c3f; protocol SHA-256 e3fb30c4705e8e40511ca4007811ec742c97b346abcdfb0039844cee5f4ece39; code SHA-256 values morning_hedge_attribution.py=36ec51840e6a5ff77ca9403e6557199963bd6b6ec40077bbdcfa965808e129cb; aggregate output SHA-256 be9166d4d3603bb94c4e67058017e8bc2da53f6136121d2e33d36328ad5b3732; execution SHA-256 ac3a686629a14629c7fa8fdcb07bdbcd5887b9f05a9ac2f4aa0ae29b1775d43c; manifest SHA-256 f029a778ee59fd27dafe37e561fc8f4a4e7a4a28f37f126dc920f3f340291a47; output-file SHA-256 values aggregate.json=be9166d4d3603bb94c4e67058017e8bc2da53f6136121d2e33d36328ad5b3732, bootstrap-draws.json=9a410eab683ebc882af862f535a2b4f677bc86c3e7055074c882ea224ec087e5, private-primitive-rows.json=ba6728adaa6e00c95ded3b9477624827d269332f50c483050a09a356f6036f9e.
Independent validation PASS, 2189579 checks, 0 mismatches, max error 8.585629984736443e-10; checker independent raw-source cash-flow and bootstrap checker (b3b4029c6536ab1903d8433a9f22d7215c3f1e0f04252d3cef149d36a1930c80); receipt 011edba0f0bd7949e78ac1662551945d1298d1b9f8a8b3ece5c048f7372558bf.
Source 2023: evaluated SHA 64e72887b782fdf838257a09877ffb817dfbfbdf; manifest SHA-256 99d2b5fd64a6180a71e5e0513e2e58b4b4199ccc707ebaeb6eb802b99ae099c7; output SHA-256 values coverage.json=500b666953b678959d0e30ad5393f5ce6549142600d58361b50d43fb3f50a556, row-ledgers.json=f413ad27f84407a28f152b1339d2cd5ba93de7057fddc3001d38494cf1161e04, source-audit.json=3b9b702a813716308202a35e002437ab4e8686a816ec53eef3625f708f93698e, summary.json=22f712dbd9b63483035b3907f884848cc9bdadb6992dca1fec24333215113404.
Source 2025: evaluated SHA db5d980c7abc344af02e8ae98fc426da92df433e; manifest SHA-256 237c589993798479c26243a1d66acec3a04fc7c8c1b4cebf4a97e4958e583d0e; output SHA-256 values case-ledgers.json=17a11c5cb21fcf00109a5f9b80f16aca8dc5be104f0d8c16e37daae2f8bcf638, coverage.json=d95911453ae38ff5fab8b18dec68cc645894968d5c5cce12ca9f55aa4c6a1f53, draw-metadata.json=bff07fc0d4419a6d4c26b97d2f9e7d5314748917d3de5c39bbd9225b4d19a8b6, normalized-selection-receipt.json=5d56bfb7c0f69022cb0b2e8e319c9f3f72b9679b29982db6f01b3cd4c4d54e19, parity.json=18d6e8358b52586f0cf1207ca02eccf8dbcfa4110a9909c76e8a6d4bb9c71816, source-audit.json=5230e814b168bb546ab5de99093899c3252f538204336ca3f46a9bee370a11ff, stderr.log=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855, stdout.log=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855, summaries.json=29a68896ee23d5cf02237ca089bc7725765877d135130a4040486bf0f9dbf02b, summary.json=c71e9b7a434fea671c2c63716fb7d2d38e6e7a608a1b69c494da5e146bdea82a, uncertainty.json=b9b43b4978d8fa8ddd3ca5527caa64318f8be1f7e131ae056d5221e361271442.
Renderer input SHA-256 1d5702022d60cb0bf89e50aaece1b2c2d2c762704c580400c6c02a5c7305881e; renderer SHA-256 da424fee394728e081449afbd9e3cca7cf7234ab2bba943cb77524d5439a9d23.


## Risk, contribution, and costs
Residual position counts, overnight price contribution, costs, notional, and drawdown describe the primary morning-price scenario.

| Long positions | Short positions | Nonzero positions |
|---|---|---|
| 33 | 36 | 69 |

Residual share exposure

| Measure | Mean shares | Total shares |
|---|---|---|
| Signed residual shares | -15.31 | -3,000.00 |

P&L contribution, mean and total USD

| Measure | Mean USD | Total USD |
|---|---|---|
| Overnight price contribution | $82.96 | $16,260.00 |
| Gross P&L | $58.43 | $11,452.43 |
| Net P&L | -$48.96 | -$9,596.60 |

Cost components, mean and total

| Component | Mean | Total |
|---|---|---|
| hedge_funding | $48.03 | $9,414.52 |
| option_fees | $7.15 | $1,401.40 |
| premium_debit_funding | $0.01 | $1.96 |
| residual_short_borrow | $10.72 | $2,102.06 |
| stock_fees | $4.34 | $850.00 |
| stock_slippage | $37.14 | $7,279.09 |

Notional and drawdown

| Maximum notional | Maximum peak-to-trough drawdown |
|---|---|
| $476,880.00 | $23,950.32 |

## Month cohorts

| Month | n | Mean | Median | Total | Long positions | Short positions | Nonzero positions |
|---|---|---|---|---|---|---|---|
| 2023-01 | 15 | -$317.49 | -$104.88 | -$4,762.35 | 1 | 4 | 5 |
| 2023-02 | 15 | $207.01 | -$7.15 | $3,105.16 | 2 | 4 | 6 |
| 2023-03 | 19 | -$291.41 | -$120.33 | -$5,536.82 | 2 | 3 | 5 |
| 2023-04 | 15 | $660.30 | $76.66 | $9,904.54 | 4 | 3 | 7 |
| 2023-05 | 17 | -$165.66 | -$53.58 | -$2,816.28 | 3 | 1 | 4 |
| 2023-06 | 17 | -$424.32 | -$86.77 | -$7,213.46 | 2 | 6 | 8 |
| 2023-07 | 14 | -$131.94 | -$111.86 | -$1,847.10 | 2 | 3 | 5 |
| 2023-08 | 19 | $95.49 | -$17.15 | $1,814.38 | 7 | 2 | 9 |
| 2023-09 | 16 | -$856.56 | -$145.14 | -$13,705.02 | 3 | 2 | 5 |
| 2023-10 | 17 | $542.12 | $62.85 | $9,215.96 | 4 | 2 | 6 |
| 2023-11 | 16 | $11.85 | -$104.38 | $189.59 | 2 | 2 | 4 |
| 2023-12 | 16 | $128.42 | -$147.43 | $2,054.79 | 1 | 4 | 5 |

## Slippage, costs, funding, and fills
The table varies fill convention, base or stress costs, stock slippage, and funding treatment for the fixed morning-price rule.

| Arm | Fill | Cost | bp | Funding | Mean net USD | Win rate |
|---|---|---|---|---|---|---|
| morning-price rule | midpoint | base | 0 | gross_prefunding | $5.83 | 48.0% |
| morning-price rule | midpoint | base | 0 | assignment_cash_net | $38.05 | 56.1% |
| morning-price rule | midpoint | base | 1 | gross_prefunding | -$31.31 | 43.9% |
| morning-price rule | midpoint | base | 1 | assignment_cash_net | $0.91 | 52.0% |
| morning-price rule | midpoint | base | 5 | gross_prefunding | -$179.86 | 34.7% |
| morning-price rule | midpoint | base | 5 | assignment_cash_net | -$147.64 | 37.8% |
| morning-price rule | midpoint | stress | 0 | gross_prefunding | -$80.92 | 38.8% |
| morning-price rule | midpoint | stress | 0 | assignment_cash_net | -$16.49 | 52.6% |
| morning-price rule | midpoint | stress | 1 | gross_prefunding | -$118.06 | 35.7% |
| morning-price rule | midpoint | stress | 1 | assignment_cash_net | -$53.63 | 46.9% |
| morning-price rule | midpoint | stress | 5 | gross_prefunding | -$266.61 | 31.1% |
| morning-price rule | midpoint | stress | 5 | assignment_cash_net | -$202.18 | 33.2% |
| morning-price rule | halfway | base | 0 | gross_prefunding | -$3.00 | 45.9% |
| morning-price rule | halfway | base | 0 | assignment_cash_net | $29.22 | 54.6% |
| morning-price rule | halfway | base | 1 | gross_prefunding | -$40.13 | 42.3% |
| morning-price rule | halfway | base | 1 | assignment_cash_net | -$7.92 | 50.0% |
| morning-price rule | halfway | base | 5 | gross_prefunding | -$188.69 | 33.7% |
| morning-price rule | halfway | base | 5 | assignment_cash_net | -$156.47 | 36.7% |
| morning-price rule | halfway | stress | 0 | gross_prefunding | -$89.75 | 38.3% |
| morning-price rule | halfway | stress | 0 | assignment_cash_net | -$25.32 | 52.0% |
| morning-price rule | halfway | stress | 1 | gross_prefunding | -$126.89 | 35.2% |
| morning-price rule | halfway | stress | 1 | assignment_cash_net | -$62.46 | 44.9% |
| morning-price rule | halfway | stress | 5 | gross_prefunding | -$275.44 | 30.6% |
| morning-price rule | halfway | stress | 5 | assignment_cash_net | -$211.01 | 32.7% |
| morning-price rule | full_cross | base | 0 | gross_prefunding | -$11.82 | 43.9% |
| morning-price rule | full_cross | base | 0 | assignment_cash_net | $20.39 | 52.6% |
| morning-price rule | full_cross | base | 1 | gross_prefunding | -$48.96 | 40.3% |
| morning-price rule | full_cross | base | 1 | assignment_cash_net | -$16.75 | 48.0% |
| morning-price rule | full_cross | base | 5 | gross_prefunding | -$197.52 | 32.1% |
| morning-price rule | full_cross | base | 5 | assignment_cash_net | -$165.30 | 34.2% |
| morning-price rule | full_cross | stress | 0 | gross_prefunding | -$98.58 | 37.2% |
| morning-price rule | full_cross | stress | 0 | assignment_cash_net | -$34.15 | 49.5% |
| morning-price rule | full_cross | stress | 1 | gross_prefunding | -$135.72 | 34.2% |
| morning-price rule | full_cross | stress | 1 | assignment_cash_net | -$71.28 | 43.4% |
| morning-price rule | full_cross | stress | 5 | gross_prefunding | -$284.27 | 29.6% |
| morning-price rule | full_cross | stress | 5 | assignment_cash_net | -$219.84 | 31.6% |

## Legacy period means
The historical comparison preserves the reviewed period means. The 2023 sample is shown separately and is not paired with 2025.

| Period | n | Mean | Median | Total | 95% CI | Win rate |
|---|---|---|---|---|---|---|
| 2019 pilot | 9 | -$610.75 | n/a | n/a | n/a | n/a |
| 2022 H2 | 63 | -$136.85 | n/a | n/a | n/a | n/a |
| 2024 | 195 | -$90.03 | n/a | n/a | n/a | n/a |
| 2025 Jan-Aug | 127 | $653.39 | -$10.08 | $82,980.62 | [$125.64, $1,274.85] | 48.0% |
| 2023 calendar year | 196 | -$48.96 | -$66.70 | -$9,596.60 | [-$221.01, $117.67] | 40.3% |

## Method and limitations

The fixed rule sets q to 1,000 shares when the official SPY open on the expiry session is at least the frozen entry-selected SPY strike plus $0.01; otherwise q is zero. The comparison tolerance is 1e-10. The morning price input chooses hedge size. It is not the modeled purchase price. The modeled hedge is bought at expiry close, then residual stock is closed at the next open. The 2023 quote clock is unverified. Some 2023 option examples and 2019–2025 stock history were inspected earlier; the entire new 68,903-row quote export was not. The 2023 sample is an additional historical replication, not a globally untouched or predictive holdout. The 2025 sample covers January through August only, not a full year, and is not paired inference against 2023. Daily theoretical fills do not prove execution, capacity, funding availability, or margin. Physical assignment is a proxy; early assignment remains possible. Do not extend the 2024/2025 15:59 quote claim to 2023. Cboe actual SPXW PM settlement is not ordinary SPX close. The oracle uses future assignment information and is diagnostic only, not a tradable rule or profit bound. No tuned rule, profit guarantee, or trading recommendation is implied.

Costs: 11 option contracts at $0.65 base / $1.50 stress each; stock fees $0.005 / $0.01 per share; annual borrow 3% / 10%; funding 5% / 10%; SPY and SPXW option contract multipliers are 100; package ratio is ten SPY options short to one SPXW option long. Bootstrap uses shared expiry ISO week clusters, 10,000 draws, seed 20261030, linear type-7 quantiles.

Sources: WRDS queries [11847843](https://wrds-www.wharton.upenn.edu/query-manager/query/11847843/) and [11847851](https://wrds-www.wharton.upenn.edu/query-manager/query/11847851/); Cboe W/M/S 2023 settlement files [https://www.cboe.com/index_settlement_values/get_sv_data/W/2023/](https://www.cboe.com/index_settlement_values/get_sv_data/W/2023/), [https://www.cboe.com/index_settlement_values/get_sv_data/M/2023/](https://www.cboe.com/index_settlement_values/get_sv_data/M/2023/), [https://www.cboe.com/index_settlement_values/get_sv_data/S/2023/](https://www.cboe.com/index_settlement_values/get_sv_data/S/2023/).

## Provenance

Validation PASS, 1777327 checks, receipt SHA-256 4e297cb6a8c941c9dce33532c7355aad4d3ce0d39d30a105d42aeab1e4b0cba3; max error 5.2523319027386606e-11.
Git 64e72887b782fdf838257a09877ffb817dfbfbdf clean=True; displayed command (private paths redacted): [local path] -m spyspx.morning_hedge_2023 evaluate --input-manifest [local path] --input-manifest-sha256 47972793ea9daadfa35e5fa7aea884f61759d750525384946f18994dc1b89656 --selection [local path] --selection-sha256 00cff4fb8c3ec13d9ea72cc4ee4d4c5cc1723747159bdea723305e2c6a167f13 --out planning/morning-hedge-replication-20261030/evaluation-01. The exact executed command is retained in the bound private execution receipt.

Input manifest 47972793ea9daadfa35e5fa7aea884f61759d750525384946f18994dc1b89656; protocol 8f66787ce63d47771c1bbb5edd516c02d46ebc37b2538f3581ae3e073cbfa403; calendar 122296e11825bbdec9af5bbed5cca5f3fc6c8ea0dc99548351dc05d44beee809; selection 00cff4fb8c3ec13d9ea72cc4ee4d4c5cc1723747159bdea723305e2c6a167f13; adapter output 6cf57c05e5ab8151d2e711fbff39437a93b821320def08141565460a15f3bb8c; execution 3b50a9eea10ee0574f9fb2f6162ff491463503c50107415448d34a9865cc766a.
Adapter code hashes: code_adapter=02cd50de29e5c843a2bbace14ce1825d6027ea2268eec105878396a2030b8a13, code_admission=c9ab3d063535b588ab0f9d42f2d8549e6f6d711942a6aff2cc2cca9f8439a506, code_expiry_extension=6a5964a78334cbe2d8fa3f1285221223eb609daeb39061036e62a022f9c481d0, code_expiry_payoff=c7eaf0c90fd5e029dac3012630af88646c0c8329697279a198ffd4842a8fbb48, code_normalizer=045971a5b41c83d311b40f6733a7c20578b5e326ada4fdbc0417a9e1506a8130, code_overnight_hedge=6cca6772325e7d55c8a85ef6a444681d2a54175e9ddfb10949dfdae6748337f3, code_replication=c010d765e58d0130b3f61b4253a8e1e08ca068b5e7a920c69e424e12952e59b8.
Legacy statistics 295078e0fa11b339cfa995786b9536ca8240c8ff98c9911f33684ec69ccfcb55; render input 1d5702022d60cb0bf89e50aaece1b2c2d2c762704c580400c6c02a5c7305881e; renderer da424fee394728e081449afbd9e3cca7cf7234ab2bba943cb77524d5439a9d23; PDF 00758646ff7464ea510ab15c731f1f861520b6e8df60818fdce61f66ee3a6e68.
