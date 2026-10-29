# Morning SPY hedge assessment

Report date: 2026-10-30

## Approved verdict

The 2025 profit did not repeat descriptively in 2023. Across 196 expiry pairs, the main morning rule lost $48.96 per package after modeled costs.
Mean gross profit was $58.43 per package and modeled costs were $107.39. The 95% expiry-week cluster interval for net mean profit was -$221.01 to $117.67, so a positive expected profit is not established.
The morning rule improved the 2023 mean relative to the unhedged control by $75.58, but its paired confidence interval also includes zero. Residual overnight stock positions remained in 69 of 196 pairs.
This separate quote period does not establish a reliable after-cost edge. It is a historical daily-price calculation, with prior data exposure and execution limitations.

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

The oracle uses future assignment information. It is diagnostic only, not a tradable rule or profit bound.

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

The fixed rule sets q to 1,000 shares when the official SPY open on the expiry session is at least the frozen entry-selected SPY strike plus $0.01; otherwise q is zero. The comparison tolerance is 1e-10. The morning price input chooses hedge size. It is not the modeled purchase price. The modeled hedge is bought at expiry close, then residual stock is closed at the next open. The 2023 quote clock is unverified. Some 2023 option examples and 2019–2025 stock history were inspected earlier; the entire new 68,903-row quote export was not. The 2023 sample is an additional historical replication, not a globally untouched or predictive holdout. The 2025 sample covers January through August only, not a full year, and is not paired inference against 2023. Daily theoretical fills do not prove execution, capacity, funding availability, or margin. Physical assignment is a proxy; early assignment remains possible. Do not extend the 2024/2025 15:59 quote claim to 2023. Cboe actual SPXW PM settlement is not ordinary SPX close. No tuned rule, profit guarantee, or trading recommendation is implied.

Costs: 11 option contracts at $0.65 base / $1.50 stress each; stock fees $0.005 / $0.01 per share; annual borrow 3% / 10%; funding 5% / 10%; SPY and SPXW option contract multipliers are 100; package ratio is ten SPY options short to one SPXW option long. Bootstrap uses shared expiry ISO week clusters, 10,000 draws, seed 20261030, linear type-7 quantiles.

Sources: WRDS queries [11847843](https://wrds-www.wharton.upenn.edu/query-manager/query/11847843/) and [11847851](https://wrds-www.wharton.upenn.edu/query-manager/query/11847851/); Cboe W/M/S 2023 settlement files [https://www.cboe.com/index_settlement_values/get_sv_data/W/2023/](https://www.cboe.com/index_settlement_values/get_sv_data/W/2023/), [https://www.cboe.com/index_settlement_values/get_sv_data/M/2023/](https://www.cboe.com/index_settlement_values/get_sv_data/M/2023/), [https://www.cboe.com/index_settlement_values/get_sv_data/S/2023/](https://www.cboe.com/index_settlement_values/get_sv_data/S/2023/).

## Provenance

Validation PASS, 1777327 checks, receipt SHA-256 4e297cb6a8c941c9dce33532c7355aad4d3ce0d39d30a105d42aeab1e4b0cba3; max error 5.2523319027386606e-11.
Git 64e72887b782fdf838257a09877ffb817dfbfbdf clean=True; displayed command (private paths redacted): [local path] -m spyspx.morning_hedge_2023 evaluate --input-manifest [local path] --input-manifest-sha256 47972793ea9daadfa35e5fa7aea884f61759d750525384946f18994dc1b89656 --selection [local path] --selection-sha256 00cff4fb8c3ec13d9ea72cc4ee4d4c5cc1723747159bdea723305e2c6a167f13 --out planning/morning-hedge-replication-20261030/evaluation-01. The exact executed command is retained in the bound private execution receipt.

Input manifest 47972793ea9daadfa35e5fa7aea884f61759d750525384946f18994dc1b89656; protocol 8f66787ce63d47771c1bbb5edd516c02d46ebc37b2538f3581ae3e073cbfa403; calendar 122296e11825bbdec9af5bbed5cca5f3fc6c8ea0dc99548351dc05d44beee809; selection 00cff4fb8c3ec13d9ea72cc4ee4d4c5cc1723747159bdea723305e2c6a167f13; adapter output 6cf57c05e5ab8151d2e711fbff39437a93b821320def08141565460a15f3bb8c; execution 3b50a9eea10ee0574f9fb2f6162ff491463503c50107415448d34a9865cc766a.
Adapter code hashes: code_adapter=02cd50de29e5c843a2bbace14ce1825d6027ea2268eec105878396a2030b8a13, code_admission=c9ab3d063535b588ab0f9d42f2d8549e6f6d711942a6aff2cc2cca9f8439a506, code_expiry_extension=6a5964a78334cbe2d8fa3f1285221223eb609daeb39061036e62a022f9c481d0, code_expiry_payoff=c7eaf0c90fd5e029dac3012630af88646c0c8329697279a198ffd4842a8fbb48, code_normalizer=045971a5b41c83d311b40f6733a7c20578b5e326ada4fdbc0417a9e1506a8130, code_overnight_hedge=6cca6772325e7d55c8a85ef6a444681d2a54175e9ddfb10949dfdae6748337f3, code_replication=c010d765e58d0130b3f61b4253a8e1e08ca068b5e7a920c69e424e12952e59b8.
Legacy statistics 295078e0fa11b339cfa995786b9536ca8240c8ff98c9911f33684ec69ccfcb55; render input fd15e0ec4f75c9d854a345533f3565fd429b8f443ce2ebb702495764c21f837d; renderer 1e14792462300df2f204564846b6af1c5167cbc067094a0391c94ea3f80248f0; PDF 2c3640bd158d5a6e86a445b5a327d9f354bd55fa40b859679190475805e41663.
