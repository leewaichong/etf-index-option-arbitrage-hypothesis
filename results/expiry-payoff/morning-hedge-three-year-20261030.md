# Morning-hedge comparison across three years

January through August 2025 was the only one of these three samples with a positive mean net result. The same morning-price hedge lost money in 2023 and 2024, including both January-August comparisons. The 2025 median was still negative, and removing its ten largest winners changes its remaining mean to a loss. These historical comparisons do not establish a repeatable after-cost edge.

## Results

The comparison uses ten short SPY options and one long SPXW option, with a 100 multiplier per contract. All figures are USD per package under the selected full-cross, base-cost, gross-prefunding, 1 bp stock-slippage case. The morning SPY open selects whether the stock hedge is 1,000 shares, using the frozen selected strike plus $0.01 threshold. The modeled stock purchase occurs at expiry close, and any residual position closes at the next session open. This morning-price hedge was a secondary arm in the study; it does not replace the original fixed-500-share primary rule.

| Period | Pairs | Mean net P&L | Median | Positive share |
|---|---:|---:|---:|---:|
| 2023 full year | 196 | -$48.96 | -$66.70 | 40.3% |
| 2024 full year | 195 | -$90.03 | -$57.16 | 39.0% |
| 2023 Jan-Aug | 131 | -$56.12 | -$47.16 | 41.2% |
| 2024 Jan-Aug | 131 | -$146.26 | -$65.13 | 38.2% |
| 2025 Jan-Aug | 127 | +$653.39 | -$10.08 | 48.0% |

For full-year 2024, the unhedged control averaged -$508.10. The morning hedge improved that mean by $418.07 per package. Its paired 95% interval was [$132.92, $714.32]. The 2024 hedged mean interval was [-$279.89, $99.65]. For the 2025 January-August cohort, the mean interval was [$125.64, $1,274.85]. These are within-year descriptive intervals. The samples were already inspected. They are not holdouts.

## Monthly means

USD per package, January through August. The complete aggregate summary includes every monthly cohort field.

| Year | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2023 | -$317.49 | +$207.01 | -$291.41 | +$660.30 | -$165.66 | -$424.32 | -$131.94 | +$95.49 |
| 2024 | -$0.20 | -$470.75 | -$462.13 | -$356.23 | -$8.87 | -$550.27 | +$626.51 | -$18.66 |
| 2025 | -$107.17 | +$816.54 | +$859.12 | +$1,017.19 | +$1,612.49 | +$784.83 | +$171.21 | -$17.94 |

## Sensitivities

The 2025 January-August mean falls to -$105.30 after removing its ten largest results, leaving 117 pairs. Removing five leaves 122 pairs and a +$152.59 mean. These are post-hoc fixed-count checks, not filters. The public JSON retains the full set of cohort and tail-removal summaries.

In the focal full-cross, base-cost, 1 bp stock-slippage, gross-prefunding case, the 2024 full-year mean was -$90.03. In the optimistic full-cross, base-cost, zero-stock-slippage, assignment-cash-net funding case, it was +$13.54 across 195 pairs. Results vary with funding assumptions; the aggregate JSON retains the full sensitivity grid.

No confidence interval is reported for the common January-August year comparisons, and no between-year p-values were calculated. The study does not estimate a predictive year effect.

## Timing and limits

The option quotes are verified at 15:59 for 2024 and 2025. The 2023 quote clock is unverified. The modeled stock purchase occurs at expiry close; residual stock closes at the next session open. These later price references do not prove executable fills, available capacity, margin, or funding. The option strategy uses one-calendar-day DTE. Stock holding can span weekends.

The 2025 sample ends in August. All historical samples had prior data exposure. Physical assignment is modeled with a proxy; early assignment and partial assignment remain unresolved. The results do not establish causality, a tradable filter, or a reliable after-cost edge. The positive 2025 mean is retained here as the exception in this sample, not as a forecast.

## Provenance

- Builder Git SHA: `1ce2763318f930f793da29293f6b5df482ef3b42`
- Builder code SHA-256: `c154660c93f5faa269742428d516cf0cd544232147eaa7a7af390a4363ce1047`
- 2023 evaluator Git SHA: `64e72887b782fdf838257a09877ffb817dfbfbdf`
- 2024/2025 evaluator Git SHA: `44ed294deddb85df594ad1e1c8a5a91bb22d08d7`
- Source aggregate SHA-256: `aa4887efd7e11f2478cb361b5ec0af37c863c324581cee2c4e3f17ff1f58aff6`
- Public aggregate summary SHA-256: `355b7823fdb3e4cf5a1868abdfcd2e00d842238e2d1e07a0254122a67b6468b4`
- Run receipt SHA-256: `f2bc5ec4f7882e0c4339384d82ed4943852a5ee4d8be2e481a3167df032b8004`
- Findings SHA-256: `5e29acbac470ac4ba2d18010d76ba609b8398c7c421dd582e4455f09dfd075c8`
- Independent three-year validation SHA-256: `4d1b55c5c2010a066a86bec07fa14402033145ff36c80bbfeba00a5c0c753876`, PASS, 2,397 checks, zero mismatches, maximum error `1.78261e-10` at tolerance `1e-7`.
- Independent validation execution record SHA-256: `bcff7d85aeb930e872d77c64f54ba8d0ee4f2b135da22ca3041ad4d2f8bd3d0e`.
- 2024 raw rerun validation record, PASS, 2,361,458 checks, zero mismatches. The available record identifier begins `b940`.

The public aggregate contains cohort, monthly, tail-removal, confidence-interval and sensitivity summaries plus provenance hashes. It omits command arguments that contained private absolute paths. No licensed quotes, individual ledgers, primitive rows or bootstrap draws are included.

The final five-page three-year assessment is available in [Markdown](../../reports/expiry-payoff/morning-hedge-assessment-20261030.md) and [PDF](../../reports/expiry-payoff/morning-hedge-assessment-20261030.pdf). PDF SHA-256: `3fb35898dccf8153a4bbda99063563c8bd5be429f44f1a210be766867bb822b7`. Markdown SHA-256: `cb4b32d31672bed36e7b97c751b73aba0d8fc9ad4436e4ad4e33c1c243bd312f`.
The earlier eight-page assessment remains in the [archive](../../reports/expiry-payoff/archive/morning-hedge-assessment-before-2024-comparison-20261030.md) with its [PDF](../../reports/expiry-payoff/archive/morning-hedge-assessment-before-2024-comparison-20261030.pdf).
