# Overnight SPY hedge assessment

Report date: 2026-10-30

## Executive assessment

Buying 500 SPY shares at the expiry close limits modeled overnight exposure to plus or minus 500 shares, but did not produce consistent profits after modeled costs. Mean net profit per package was -$190.13 in 2022, -$211.54 in 2024, and +$43.21 in 2025. Each descriptive 95% interval includes zero. In 2024, it improved the mean by $296.56 versus no hedge, but the mean remained negative.
The rule based on that morning's stock price averaged -$136.85 in 2022, -$90.03 in 2024, and +$653.39 in 2025. Its 2025 descriptive interval was +$125.64 to +$1,274.85. The median was -$10.08. It left modeled stock exposure on 48 of 127 expiries, and the overnight stock-price contribution averaged +$777.20. The positive result still involved stock risk.
The diagnostic that removes all modeled overnight shares lost money after the main cost assumptions in every period. It requires future assignment information and cannot be used as a trading rule or a guaranteed profit bound.
These are historical comparisons on previously examined periods. Live execution remains untested.

## All scenario means by period

| Scenario | Period | n | q0 | fixed500 | fixed1000 | openrule |
|---|---|---|---|---|---|---|
| Full-cross / base / gross prefunding / 1 bp | 2019 | 9 | -$827.24 | -$792.27 | -$757.30 | -$610.75 |
| Full-cross / base / gross prefunding / 1 bp | 2022 | 63 | $96.47 | -$190.13 | -$476.73 | -$136.85 |
| Full-cross / base / gross prefunding / 1 bp | 2024 | 195 | -$508.10 | -$211.54 | $85.02 | -$90.03 |
| Full-cross / base / gross prefunding / 1 bp | 2025 (Jan-Aug) | 127 | $191.97 | $43.21 | -$105.54 | $653.39 |
| Full-cross / stress / gross prefunding / 1 bp | 2019 | 9 | -$869.12 | -$866.17 | -$863.22 | -$664.49 |
| Full-cross / stress / gross prefunding / 1 bp | 2022 | 63 | $24.68 | -$284.31 | -$593.30 | -$207.19 |
| Full-cross / stress / gross prefunding / 1 bp | 2024 | 195 | -$620.13 | -$333.73 | -$47.33 | -$194.15 |
| Full-cross / stress / gross prefunding / 1 bp | 2025 (Jan-Aug) | 127 | $85.80 | -$81.51 | -$248.81 | $538.97 |
| Full-cross / base / assignment cash net / 1 bp | 2019 | 9 | -$827.24 | -$781.25 | -$735.53 | -$593.35 |
| Full-cross / base / assignment cash net / 1 bp | 2022 | 63 | $96.47 | -$168.63 | -$434.31 | -$103.63 |
| Full-cross / base / assignment cash net / 1 bp | 2024 | 195 | -$508.10 | -$175.92 | $155.85 | -$33.08 |
| Full-cross / base / assignment cash net / 1 bp | 2025 (Jan-Aug) | 127 | $191.97 | $76.82 | -$38.91 | $702.70 |
| Full-cross / stress / assignment cash net / 1 bp | 2019 | 9 | -$869.12 | -$844.13 | -$819.68 | -$629.68 |
| Full-cross / stress / assignment cash net / 1 bp | 2022 | 63 | $24.68 | -$241.31 | -$508.46 | -$140.77 |
| Full-cross / stress / assignment cash net / 1 bp | 2024 | 195 | -$620.13 | -$262.49 | $94.33 | -$80.25 |
| Full-cross / stress / assignment cash net / 1 bp | 2025 (Jan-Aug) | 127 | $85.80 | -$14.30 | -$115.55 | $637.58 |

## Primary uncertainty and cost sensitivity

The 500-share hedge was prespecified. The 2019 pilot has means only. Intervals below use full-cross, gross prefunding, and 1 bp. No-hedge absolute intervals and the full 432-case matrix are retained in this companion.

| Year | Cost | q0 mean | q0 abs 95% CI | fixed500 mean | fixed500 abs 95% CI | Paired change | Paired 95% CI |
|---|---|---|---|---|---|---|---|
| 2022 | base | $96.47 | [-$166.32, $347.98] | -$190.13 | [-$591.85, $255.63] | -$286.60 | [-$532.06, $17.88] |
| 2022 | stress | $24.68 | [-$241.07, $276.19] | -$284.31 | [-$684.79, $156.73] | -$308.99 | [-$559.12, -$2.65] |
| 2024 | base | -$508.10 | [-$795.19, -$237.03] | -$211.54 | [-$447.40, $10.25] | $296.56 | [$105.71, $479.20] |
| 2024 | stress | -$620.13 | [-$912.50, -$343.69] | -$333.73 | [-$570.32, -$110.02] | $286.40 | [$92.61, $469.91] |
| 2025 (Jan-Aug) | base | $191.97 | [-$406.29, $854.57] | $43.21 | [-$279.14, $356.71] | -$148.75 | [-$768.07, $374.28] |
| 2025 (Jan-Aug) | stress | $85.80 | [-$518.22, $759.24] | -$81.51 | [-$407.84, $234.76] | -$167.31 | [-$788.34, $355.92] |

### Base slippage sensitivity

| Slippage (bp) | Year | n | fixed500 mean USD |
|---|---|---|---|
| 0 | 2022 | 63 | -$151.03 |
| 0 | 2024 | 195 | -$157.42 |
| 0 | 2025 (Jan-Aug) | 127 | $102.56 |
| 1 | 2022 | 63 | -$190.13 |
| 1 | 2024 | 195 | -$211.54 |
| 1 | 2025 (Jan-Aug) | 127 | $43.21 |
| 5 | 2022 | 63 | -$346.51 |
| 5 | 2024 | 195 | -$428.03 |
| 5 | 2025 (Jan-Aug) | 127 | -$194.18 |

### Stress slippage sensitivity

| Slippage (bp) | Year | n | fixed500 mean USD |
|---|---|---|---|
| 0 | 2022 | 63 | -$245.21 |
| 0 | 2024 | 195 | -$279.61 |
| 0 | 2025 (Jan-Aug) | 127 | -$22.16 |
| 1 | 2022 | 63 | -$284.31 |
| 1 | 2024 | 195 | -$333.73 |
| 1 | 2025 (Jan-Aug) | 127 | -$81.51 |
| 5 | 2022 | 63 | -$440.70 |
| 5 | 2024 | 195 | -$550.22 |
| 5 | 2025 (Jan-Aug) | 127 | -$318.89 |

### Funding assumption at 1 bp

Gross prefunding charges funding on the full stock purchase. Assignment-cash net credits modeled assignment cash against that need. This optimistic accounting contrast does not show that a broker would settle or release funds in time.

| Assumption | Period | Cost | n | fixed500 mean USD |
|---|---|---|---|---|
| assignment_cash_net | 2022 | base | 63 | -$168.63 |
| assignment_cash_net | 2022 | stress | 63 | -$241.31 |
| assignment_cash_net | 2024 | base | 195 | -$175.92 |
| assignment_cash_net | 2024 | stress | 195 | -$262.49 |
| assignment_cash_net | 2025 (Jan-Aug) | base | 127 | $76.82 |
| assignment_cash_net | 2025 (Jan-Aug) | stress | 127 | -$14.30 |
| gross_prefunding | 2022 | base | 63 | -$190.13 |
| gross_prefunding | 2022 | stress | 63 | -$284.31 |
| gross_prefunding | 2024 | base | 195 | -$211.54 |
| gross_prefunding | 2024 | stress | 195 | -$333.73 |
| gross_prefunding | 2025 (Jan-Aug) | base | 127 | $43.21 |
| gross_prefunding | 2025 (Jan-Aug) | stress | 127 | -$81.51 |

## Capital and residual exposure

Buy at the close. Sell a residual long or buy back a residual short at the next open. End flat. The morning-price rule sizes its hedge from the expiry-session SPY open and frozen SPY strike, known before the closing decision. It does not use assignment or the expiry close. Availability of a later order is unverified. Gross stock-purchase notional is separate from total required capital or margin.

### 2022 risk summary, n=63

| Case | Gross stock purchase USD | Max stock notional USD | Peak-to-trough cash drawdown USD | Residual count | Long count | Short count | Residual SD shares |
|---|---|---|---|---|---|---|---|
| fixed1000 | $427,100.00 | $427,100.00 | $34,376.14 | 35 | 35 | 0 | 500.90 |
| fixed500 | $213,550.00 | $213,550.00 | $16,201.14 | 63 | 35 | 28 | 500.90 |
| openrule | $427,100.00 | $427,100.00 | $11,462.52 | 13 | 8 | 5 | 455.38 |
| q0 | $0.00 | $424,765.00 | $5,772.48 | 28 | 0 | 28 | 500.90 |
### 2024 risk summary, n=195

| Case | Gross stock purchase USD | Max stock notional USD | Peak-to-trough cash drawdown USD | Residual count | Long count | Short count | Residual SD shares |
|---|---|---|---|---|---|---|---|
| fixed1000 | $607,810.00 | $607,810.00 | $29,122.70 | 81 | 81 | 0 | 494.06 |
| fixed500 | $303,905.00 | $303,905.00 | $47,887.24 | 195 | 81 | 114 | 494.06 |
| openrule | $607,810.00 | $607,810.00 | $30,912.20 | 50 | 27 | 23 | 507.26 |
| q0 | $0.00 | $607,690.00 | $103,924.65 | 114 | 0 | 114 | 494.06 |
### 2025 (Jan-Aug) risk summary, n=127

| Case | Gross stock purchase USD | Max stock notional USD | Peak-to-trough cash drawdown USD | Residual count | Long count | Short count | Residual SD shares |
|---|---|---|---|---|---|---|---|
| fixed1000 | $648,920.00 | $648,920.00 | $59,411.47 | 58 | 58 | 0 | 500.09 |
| fixed500 | $324,460.00 | $324,460.00 | $31,235.90 | 127 | 58 | 69 | 500.09 |
| openrule | $648,920.00 | $648,920.00 | $19,438.73 | 48 | 27 | 21 | 615.39 |
| q0 | $0.00 | $647,470.00 | $30,116.01 | 69 | 0 | 69 | 500.09 |

Partial assignment is unobserved. Long and short residuals are possible. A zero no-hedge stock purchase does not mean zero total capital. Gross stock purchases and maximum stock notional do not measure total capital or margin. No margin estimate is supplied.

Costs: 11 option contracts at $0.65 each base and $1.50 stress; stock commission $0.005/share base and $0.010/share stress; borrow 3.0%/10.0%; funding 5.0%/10.0%; slippage 0, 1, 5 bp. Dividends: Unconditional cash dividend equals residual shares multiplied by the dividend per share.

### Oracle diagnostic

Oracle uses future assignment information. It is not a tradable rule, is not ranked with the candidate strategies, and is not a guaranteed-profit upper bound.

| Period | n | Full-cross/base/gross/1 bp mean USD | 95% CI |
|---|---|---|---|
| 2019 | 9 | -$63.75 | Means only |
| 2022 | 63 | -$85.27 | [-$134.93, -$42.02] |
| 2024 | 195 | -$71.93 | [-$101.81, -$43.30] |
| 2025 (Jan-Aug) | 127 | -$90.96 | [-$214.95, -$4.56] |

## Complete uncertainty inputs

The following 432 rows preserve every nonzero strategy case: 2022/2024/2025, three fills, two cost modes, 0/1/5 bp, and two funding assumptions. Each row retains absolute and paired-versus-q0 estimates and intervals.

| Year | Strategy | Fill | Cost | Slippage bp | Funding | n | Mean | Absolute 95% CI | Paired mean | Paired 95% CI |
|---|---|---|---|---|---|---|---|---|---|---|
| 2022 | assignmentoracle | full_cross | base | 0 | assignment_cash_net | 63 | -$25.24 | [-$74.79, $15.10] | -$139.30 | [-$392.26, $124.78] |
| 2022 | assignmentoracle | full_cross | base | 0 | gross_prefunding | 63 | -$67.66 | [-$116.17, -$25.93] | -$181.72 | [-$435.81, $80.97] |
| 2022 | assignmentoracle | full_cross | base | 1 | assignment_cash_net | 63 | -$42.85 | [-$92.15, -$2.81] | -$139.32 | [-$392.30, $124.79] |
| 2022 | assignmentoracle | full_cross | base | 1 | gross_prefunding | 63 | -$85.27 | [-$134.93, -$42.02] | -$181.74 | [-$435.86, $80.98] |
| 2022 | assignmentoracle | full_cross | base | 5 | assignment_cash_net | 63 | -$113.29 | [-$165.06, -$68.04] | -$139.39 | [-$392.47, $124.82] |
| 2022 | assignmentoracle | full_cross | base | 5 | gross_prefunding | 63 | -$155.71 | [-$211.68, -$103.74] | -$181.81 | [-$436.02, $81.02] |
| 2022 | assignmentoracle | full_cross | stress | 0 | assignment_cash_net | 63 | -$37.40 | [-$86.84, $2.89] | -$79.68 | [-$331.83, $186.76] |
| 2022 | assignmentoracle | full_cross | stress | 0 | gross_prefunding | 63 | -$122.24 | [-$173.94, -$74.33] | -$164.52 | [-$418.23, $97.53] |
| 2022 | assignmentoracle | full_cross | stress | 1 | assignment_cash_net | 63 | -$55.02 | [-$104.28, -$15.02] | -$79.70 | [-$331.87, $186.77] |
| 2022 | assignmentoracle | full_cross | stress | 1 | gross_prefunding | 63 | -$139.86 | [-$193.62, -$89.95] | -$164.54 | [-$418.27, $97.54] |
| 2022 | assignmentoracle | full_cross | stress | 5 | assignment_cash_net | 63 | -$125.46 | [-$177.38, -$79.88] | -$79.77 | [-$332.04, $186.81] |
| 2022 | assignmentoracle | full_cross | stress | 5 | gross_prefunding | 63 | -$210.30 | [-$274.40, -$148.00] | -$164.61 | [-$418.44, $97.57] |
| 2022 | assignmentoracle | halfway | base | 0 | assignment_cash_net | 63 | -$13.53 | [-$62.84, $26.66] | -$139.30 | [-$392.26, $124.78] |
| 2022 | assignmentoracle | halfway | base | 0 | gross_prefunding | 63 | -$55.95 | [-$104.09, -$14.67] | -$181.72 | [-$435.81, $80.97] |
| 2022 | assignmentoracle | halfway | base | 1 | assignment_cash_net | 63 | -$31.14 | [-$80.23, $8.87] | -$139.32 | [-$392.30, $124.79] |
| 2022 | assignmentoracle | halfway | base | 1 | gross_prefunding | 63 | -$73.56 | [-$122.75, -$30.64] | -$181.74 | [-$435.86, $80.98] |
| 2022 | assignmentoracle | halfway | base | 5 | assignment_cash_net | 63 | -$101.58 | [-$152.98, -$56.51] | -$139.39 | [-$392.47, $124.82] |
| 2022 | assignmentoracle | halfway | base | 5 | gross_prefunding | 63 | -$144.00 | [-$199.60, -$92.18] | -$181.81 | [-$436.02, $81.02] |
| 2022 | assignmentoracle | halfway | stress | 0 | assignment_cash_net | 63 | -$25.69 | [-$74.95, $14.41] | -$79.68 | [-$331.83, $186.76] |
| 2022 | assignmentoracle | halfway | stress | 0 | gross_prefunding | 63 | -$110.53 | [-$162.00, -$63.07] | -$164.52 | [-$418.23, $97.53] |
| 2022 | assignmentoracle | halfway | stress | 1 | assignment_cash_net | 63 | -$43.30 | [-$92.23, -$3.26] | -$79.70 | [-$331.87, $186.77] |
| 2022 | assignmentoracle | halfway | stress | 1 | gross_prefunding | 63 | -$128.15 | [-$181.55, -$78.51] | -$164.54 | [-$418.27, $97.54] |
| 2022 | assignmentoracle | halfway | stress | 5 | assignment_cash_net | 63 | -$113.75 | [-$165.38, -$68.51] | -$79.77 | [-$332.04, $186.81] |
| 2022 | assignmentoracle | halfway | stress | 5 | gross_prefunding | 63 | -$198.59 | [-$262.43, -$136.64] | -$164.61 | [-$418.44, $97.57] |
| 2022 | assignmentoracle | midpoint | base | 0 | assignment_cash_net | 63 | -$1.82 | [-$50.94, $38.39] | -$139.30 | [-$392.26, $124.78] |
| 2022 | assignmentoracle | midpoint | base | 0 | gross_prefunding | 63 | -$44.24 | [-$92.03, -$3.02] | -$181.72 | [-$435.81, $80.97] |
| 2022 | assignmentoracle | midpoint | base | 1 | assignment_cash_net | 63 | -$19.43 | [-$68.45, $20.70] | -$139.32 | [-$392.30, $124.79] |
| 2022 | assignmentoracle | midpoint | base | 1 | gross_prefunding | 63 | -$61.85 | [-$110.92, -$19.27] | -$181.74 | [-$435.86, $80.98] |
| 2022 | assignmentoracle | midpoint | base | 5 | assignment_cash_net | 63 | -$89.88 | [-$141.28, -$45.08] | -$139.39 | [-$392.47, $124.82] |
| 2022 | assignmentoracle | midpoint | base | 5 | gross_prefunding | 63 | -$132.30 | [-$187.58, -$80.71] | -$181.81 | [-$436.02, $81.02] |
| 2022 | assignmentoracle | midpoint | stress | 0 | assignment_cash_net | 63 | -$13.98 | [-$63.17, $26.19] | -$79.68 | [-$331.83, $186.76] |
| 2022 | assignmentoracle | midpoint | stress | 0 | gross_prefunding | 63 | -$98.82 | [-$150.20, -$51.56] | -$164.52 | [-$418.23, $97.53] |
| 2022 | assignmentoracle | midpoint | stress | 1 | assignment_cash_net | 63 | -$31.59 | [-$80.47, $8.50] | -$79.70 | [-$331.87, $186.77] |
| 2022 | assignmentoracle | midpoint | stress | 1 | gross_prefunding | 63 | -$116.44 | [-$169.89, -$67.01] | -$164.54 | [-$418.27, $97.54] |
| 2022 | assignmentoracle | midpoint | stress | 5 | assignment_cash_net | 63 | -$102.04 | [-$153.65, -$57.04] | -$79.77 | [-$332.04, $186.81] |
| 2022 | assignmentoracle | midpoint | stress | 5 | gross_prefunding | 63 | -$186.88 | [-$250.58, -$125.19] | -$164.61 | [-$418.44, $97.57] |
| 2022 | fixed1000 | full_cross | base | 0 | assignment_cash_net | 63 | -$373.71 | [-$985.75, $352.30] | -$487.78 | [-$983.15, $123.07] |
| 2022 | fixed1000 | full_cross | base | 0 | gross_prefunding | 63 | -$416.13 | [-$1,020.85, $305.68] | -$530.20 | [-$1,019.56, $77.58] |
| 2022 | fixed1000 | full_cross | base | 1 | assignment_cash_net | 63 | -$434.31 | [-$1,048.36, $292.66] | -$530.78 | [-$1,028.71, $82.18] |
| 2022 | fixed1000 | full_cross | base | 1 | gross_prefunding | 63 | -$476.73 | [-$1,084.08, $244.37] | -$573.20 | [-$1,064.13, $35.77] |
| 2022 | fixed1000 | full_cross | base | 5 | assignment_cash_net | 63 | -$676.70 | [-$1,298.96, $53.31] | -$702.80 | [-$1,212.68, -$80.11] |
| 2022 | fixed1000 | full_cross | base | 5 | gross_prefunding | 63 | -$719.12 | [-$1,334.38, $9.30] | -$745.22 | [-$1,249.34, -$128.66] |
| 2022 | fixed1000 | full_cross | stress | 0 | assignment_cash_net | 63 | -$447.87 | [-$1,067.57, $281.89] | -$490.15 | [-$998.42, $129.49] |
| 2022 | fixed1000 | full_cross | stress | 0 | gross_prefunding | 63 | -$532.71 | [-$1,138.50, $186.89] | -$574.99 | [-$1,072.07, $36.01] |
| 2022 | fixed1000 | full_cross | stress | 1 | assignment_cash_net | 63 | -$508.46 | [-$1,128.80, $222.58] | -$533.15 | [-$1,045.45, $90.08] |
| 2022 | fixed1000 | full_cross | stress | 1 | gross_prefunding | 63 | -$593.30 | [-$1,201.29, $127.97] | -$617.99 | [-$1,118.24, -$5.30] |
| 2022 | fixed1000 | full_cross | stress | 5 | assignment_cash_net | 63 | -$750.86 | [-$1,377.17, -$16.59] | -$705.16 | [-$1,230.60, -$69.95] |
| 2022 | fixed1000 | full_cross | stress | 5 | gross_prefunding | 63 | -$835.70 | [-$1,450.37, -$108.81] | -$790.00 | [-$1,301.67, -$167.20] |
| 2022 | fixed1000 | halfway | base | 0 | assignment_cash_net | 63 | -$362.00 | [-$973.73, $363.72] | -$487.78 | [-$983.15, $123.07] |
| 2022 | fixed1000 | halfway | base | 0 | gross_prefunding | 63 | -$404.42 | [-$1,008.97, $317.79] | -$530.20 | [-$1,019.56, $77.58] |
| 2022 | fixed1000 | halfway | base | 1 | assignment_cash_net | 63 | -$422.60 | [-$1,036.42, $304.89] | -$530.78 | [-$1,028.71, $82.18] |
| 2022 | fixed1000 | halfway | base | 1 | gross_prefunding | 63 | -$465.02 | [-$1,072.72, $255.80] | -$573.20 | [-$1,064.13, $35.77] |
| 2022 | fixed1000 | halfway | base | 5 | assignment_cash_net | 63 | -$664.99 | [-$1,287.06, $65.37] | -$702.80 | [-$1,212.68, -$80.11] |
| 2022 | fixed1000 | halfway | base | 5 | gross_prefunding | 63 | -$707.41 | [-$1,323.04, $20.80] | -$745.22 | [-$1,249.34, -$128.66] |
| 2022 | fixed1000 | halfway | stress | 0 | assignment_cash_net | 63 | -$436.16 | [-$1,055.20, $293.67] | -$490.15 | [-$998.42, $129.49] |
| 2022 | fixed1000 | halfway | stress | 0 | gross_prefunding | 63 | -$521.00 | [-$1,126.71, $197.99] | -$574.99 | [-$1,072.07, $36.01] |
| 2022 | fixed1000 | halfway | stress | 1 | assignment_cash_net | 63 | -$496.75 | [-$1,116.80, $234.37] | -$533.15 | [-$1,045.45, $90.08] |
| 2022 | fixed1000 | halfway | stress | 1 | gross_prefunding | 63 | -$581.59 | [-$1,189.04, $139.07] | -$617.99 | [-$1,118.24, -$5.30] |
| 2022 | fixed1000 | halfway | stress | 5 | assignment_cash_net | 63 | -$739.15 | [-$1,364.77, -$4.63] | -$705.16 | [-$1,230.60, -$69.95] |
| 2022 | fixed1000 | halfway | stress | 5 | gross_prefunding | 63 | -$823.99 | [-$1,438.48, -$97.52] | -$790.00 | [-$1,301.67, -$167.20] |
| 2022 | fixed1000 | midpoint | base | 0 | assignment_cash_net | 63 | -$350.29 | [-$962.00, $375.14] | -$487.78 | [-$983.15, $123.07] |
| 2022 | fixed1000 | midpoint | base | 0 | gross_prefunding | 63 | -$392.71 | [-$997.25, $328.63] | -$530.20 | [-$1,019.56, $77.58] |
| 2022 | fixed1000 | midpoint | base | 1 | assignment_cash_net | 63 | -$410.89 | [-$1,024.82, $316.67] | -$530.78 | [-$1,028.71, $82.18] |
| 2022 | fixed1000 | midpoint | base | 1 | gross_prefunding | 63 | -$453.31 | [-$1,060.42, $267.31] | -$573.20 | [-$1,064.13, $35.77] |
| 2022 | fixed1000 | midpoint | base | 5 | assignment_cash_net | 63 | -$653.28 | [-$1,275.09, $77.51] | -$702.80 | [-$1,212.68, -$80.11] |
| 2022 | fixed1000 | midpoint | base | 5 | gross_prefunding | 63 | -$695.70 | [-$1,311.57, $32.29] | -$745.22 | [-$1,249.34, -$128.66] |
| 2022 | fixed1000 | midpoint | stress | 0 | assignment_cash_net | 63 | -$424.45 | [-$1,042.78, $305.43] | -$490.15 | [-$998.42, $129.49] |
| 2022 | fixed1000 | midpoint | stress | 0 | gross_prefunding | 63 | -$509.29 | [-$1,114.79, $209.22] | -$574.99 | [-$1,072.07, $36.01] |
| 2022 | fixed1000 | midpoint | stress | 1 | assignment_cash_net | 63 | -$485.04 | [-$1,105.07, $246.12] | -$533.15 | [-$1,045.45, $90.08] |
| 2022 | fixed1000 | midpoint | stress | 1 | gross_prefunding | 63 | -$569.88 | [-$1,177.07, $150.17] | -$617.99 | [-$1,118.24, -$5.30] |
| 2022 | fixed1000 | midpoint | stress | 5 | assignment_cash_net | 63 | -$727.44 | [-$1,352.72, $7.11] | -$705.16 | [-$1,230.60, -$69.95] |
| 2022 | fixed1000 | midpoint | stress | 5 | gross_prefunding | 63 | -$812.28 | [-$1,425.71, -$85.64] | -$790.00 | [-$1,301.67, -$167.20] |
| 2022 | fixed500 | full_cross | base | 0 | assignment_cash_net | 63 | -$129.53 | [-$533.23, $319.21] | -$243.60 | [-$491.39, $61.84] |
| 2022 | fixed500 | full_cross | base | 0 | gross_prefunding | 63 | -$151.03 | [-$552.69, $294.66] | -$265.10 | [-$509.78, $38.79] |
| 2022 | fixed500 | full_cross | base | 1 | assignment_cash_net | 63 | -$168.63 | [-$572.30, $280.10] | -$265.10 | [-$514.14, $41.44] |
| 2022 | fixed500 | full_cross | base | 1 | gross_prefunding | 63 | -$190.13 | [-$591.85, $255.63] | -$286.60 | [-$532.06, $17.88] |
| 2022 | fixed500 | full_cross | base | 5 | assignment_cash_net | 63 | -$325.01 | [-$728.64, $123.61] | -$351.11 | [-$606.12, -$39.69] |
| 2022 | fixed500 | full_cross | base | 5 | gross_prefunding | 63 | -$346.51 | [-$748.41, $100.01] | -$372.61 | [-$624.67, -$64.33] |
| 2022 | fixed500 | full_cross | stress | 0 | assignment_cash_net | 63 | -$202.21 | [-$604.20, $245.17] | -$244.49 | [-$498.81, $65.54] |
| 2022 | fixed500 | full_cross | stress | 0 | gross_prefunding | 63 | -$245.21 | [-$645.33, $195.77] | -$287.49 | [-$536.04, $18.01] |
| 2022 | fixed500 | full_cross | stress | 1 | assignment_cash_net | 63 | -$241.31 | [-$643.85, $206.05] | -$265.99 | [-$522.26, $45.65] |
| 2022 | fixed500 | full_cross | stress | 1 | gross_prefunding | 63 | -$284.31 | [-$684.79, $156.73] | -$308.99 | [-$559.12, -$2.65] |
| 2022 | fixed500 | full_cross | stress | 5 | assignment_cash_net | 63 | -$397.69 | [-$800.67, $49.96] | -$352.00 | [-$614.70, -$34.26] |
| 2022 | fixed500 | full_cross | stress | 5 | gross_prefunding | 63 | -$440.70 | [-$842.29, $0.35] | -$395.00 | [-$650.84, -$83.60] |
| 2022 | fixed500 | halfway | base | 0 | assignment_cash_net | 63 | -$117.82 | [-$521.30, $330.85] | -$243.60 | [-$491.39, $61.84] |
| 2022 | fixed500 | halfway | base | 0 | gross_prefunding | 63 | -$139.32 | [-$541.14, $306.54] | -$265.10 | [-$509.78, $38.79] |
| 2022 | fixed500 | halfway | base | 1 | assignment_cash_net | 63 | -$156.92 | [-$560.39, $291.58] | -$265.10 | [-$514.14, $41.44] |
| 2022 | fixed500 | halfway | base | 1 | gross_prefunding | 63 | -$178.42 | [-$580.29, $267.63] | -$286.60 | [-$532.06, $17.88] |
| 2022 | fixed500 | halfway | base | 5 | assignment_cash_net | 63 | -$313.30 | [-$716.87, $134.48] | -$351.11 | [-$606.12, -$39.69] |
| 2022 | fixed500 | halfway | base | 5 | gross_prefunding | 63 | -$334.81 | [-$736.93, $111.50] | -$372.61 | [-$624.67, -$64.33] |
| 2022 | fixed500 | halfway | stress | 0 | assignment_cash_net | 63 | -$190.50 | [-$593.08, $256.95] | -$244.49 | [-$498.81, $65.54] |
| 2022 | fixed500 | halfway | stress | 0 | gross_prefunding | 63 | -$233.50 | [-$633.57, $207.23] | -$287.49 | [-$536.04, $18.01] |
| 2022 | fixed500 | halfway | stress | 1 | assignment_cash_net | 63 | -$229.60 | [-$632.69, $217.89] | -$265.99 | [-$522.26, $45.65] |
| 2022 | fixed500 | halfway | stress | 1 | gross_prefunding | 63 | -$272.60 | [-$672.68, $168.09] | -$308.99 | [-$559.12, -$2.65] |
| 2022 | fixed500 | halfway | stress | 5 | assignment_cash_net | 63 | -$385.98 | [-$789.56, $61.90] | -$352.00 | [-$614.70, -$34.26] |
| 2022 | fixed500 | halfway | stress | 5 | gross_prefunding | 63 | -$428.98 | [-$830.72, $11.73] | -$395.00 | [-$650.84, -$83.60] |
| 2022 | fixed500 | midpoint | base | 0 | assignment_cash_net | 63 | -$106.11 | [-$509.10, $341.68] | -$243.60 | [-$491.39, $61.84] |
| 2022 | fixed500 | midpoint | base | 0 | gross_prefunding | 63 | -$127.62 | [-$529.58, $318.28] | -$265.10 | [-$509.78, $38.79] |
| 2022 | fixed500 | midpoint | base | 1 | assignment_cash_net | 63 | -$145.21 | [-$548.74, $302.41] | -$265.10 | [-$514.14, $41.44] |
| 2022 | fixed500 | midpoint | base | 1 | gross_prefunding | 63 | -$166.71 | [-$568.71, $279.20] | -$286.60 | [-$532.06, $17.88] |
| 2022 | fixed500 | midpoint | base | 5 | assignment_cash_net | 63 | -$301.60 | [-$705.21, $146.31] | -$351.11 | [-$606.12, -$39.69] |
| 2022 | fixed500 | midpoint | base | 5 | gross_prefunding | 63 | -$323.10 | [-$725.45, $122.81] | -$372.61 | [-$624.67, -$64.33] |
| 2022 | fixed500 | midpoint | stress | 0 | assignment_cash_net | 63 | -$178.79 | [-$581.98, $268.62] | -$244.49 | [-$498.81, $65.54] |
| 2022 | fixed500 | midpoint | stress | 0 | gross_prefunding | 63 | -$221.79 | [-$621.97, $218.81] | -$287.49 | [-$536.04, $18.01] |
| 2022 | fixed500 | midpoint | stress | 1 | assignment_cash_net | 63 | -$217.89 | [-$621.15, $229.54] | -$265.99 | [-$522.26, $45.65] |
| 2022 | fixed500 | midpoint | stress | 1 | gross_prefunding | 63 | -$260.89 | [-$661.47, $179.72] | -$308.99 | [-$559.12, -$2.65] |
| 2022 | fixed500 | midpoint | stress | 5 | assignment_cash_net | 63 | -$374.27 | [-$777.91, $73.22] | -$352.00 | [-$614.70, -$34.26] |
| 2022 | fixed500 | midpoint | stress | 5 | gross_prefunding | 63 | -$417.27 | [-$818.61, $23.45] | -$395.00 | [-$650.84, -$83.60] |
| 2022 | openrule | full_cross | base | 0 | assignment_cash_net | 63 | -$76.33 | [-$303.40, $158.76] | -$190.39 | [-$458.78, $110.28] |
| 2022 | openrule | full_cross | base | 0 | gross_prefunding | 63 | -$109.54 | [-$332.08, $122.06] | -$223.61 | [-$489.21, $75.14] |
| 2022 | openrule | full_cross | base | 1 | assignment_cash_net | 63 | -$103.63 | [-$335.05, $133.15] | -$200.11 | [-$471.41, $102.81] |
| 2022 | openrule | full_cross | base | 1 | gross_prefunding | 63 | -$136.85 | [-$363.56, $96.43] | -$233.32 | [-$501.56, $67.27] |
| 2022 | openrule | full_cross | base | 5 | assignment_cash_net | 63 | -$212.86 | [-$458.62, $30.65] | -$238.96 | [-$523.08, $74.98] |
| 2022 | openrule | full_cross | base | 5 | gross_prefunding | 63 | -$246.07 | [-$486.88, -$5.74] | -$272.17 | [-$553.27, $37.20] |
| 2022 | openrule | full_cross | stress | 0 | assignment_cash_net | 63 | -$113.46 | [-$345.52, $123.00] | -$155.74 | [-$433.19, $152.78] |
| 2022 | openrule | full_cross | stress | 0 | gross_prefunding | 63 | -$179.88 | [-$404.20, $49.72] | -$222.16 | [-$491.97, $79.96] |
| 2022 | openrule | full_cross | stress | 1 | assignment_cash_net | 63 | -$140.77 | [-$376.23, $97.12] | -$165.45 | [-$446.00, $147.85] |
| 2022 | openrule | full_cross | stress | 1 | gross_prefunding | 63 | -$207.19 | [-$433.96, $24.34] | -$231.87 | [-$504.30, $72.28] |
| 2022 | openrule | full_cross | stress | 5 | assignment_cash_net | 63 | -$249.99 | [-$503.65, -$4.83] | -$204.30 | [-$500.44, $121.32] |
| 2022 | openrule | full_cross | stress | 5 | gross_prefunding | 63 | -$316.42 | [-$562.77, -$77.59] | -$270.72 | [-$557.80, $43.58] |
| 2022 | openrule | halfway | base | 0 | assignment_cash_net | 63 | -$64.62 | [-$291.90, $170.73] | -$190.39 | [-$458.78, $110.28] |
| 2022 | openrule | halfway | base | 0 | gross_prefunding | 63 | -$97.83 | [-$321.08, $134.02] | -$223.61 | [-$489.21, $75.14] |
| 2022 | openrule | halfway | base | 1 | assignment_cash_net | 63 | -$91.93 | [-$323.31, $144.88] | -$200.11 | [-$471.41, $102.81] |
| 2022 | openrule | halfway | base | 1 | gross_prefunding | 63 | -$125.14 | [-$352.28, $108.45] | -$233.32 | [-$501.56, $67.27] |
| 2022 | openrule | halfway | base | 5 | assignment_cash_net | 63 | -$201.15 | [-$447.37, $42.26] | -$238.96 | [-$523.08, $74.98] |
| 2022 | openrule | halfway | base | 5 | gross_prefunding | 63 | -$234.36 | [-$475.61, $5.56] | -$272.17 | [-$553.27, $37.20] |
| 2022 | openrule | halfway | stress | 0 | assignment_cash_net | 63 | -$101.75 | [-$333.63, $134.44] | -$155.74 | [-$433.19, $152.78] |
| 2022 | openrule | halfway | stress | 0 | gross_prefunding | 63 | -$168.17 | [-$392.69, $61.51] | -$222.16 | [-$491.97, $79.96] |
| 2022 | openrule | halfway | stress | 1 | assignment_cash_net | 63 | -$129.06 | [-$364.78, $108.70] | -$165.45 | [-$446.00, $147.85] |
| 2022 | openrule | halfway | stress | 1 | gross_prefunding | 63 | -$195.48 | [-$422.18, $36.19] | -$231.87 | [-$504.30, $72.28] |
| 2022 | openrule | halfway | stress | 5 | assignment_cash_net | 63 | -$238.28 | [-$492.02, $7.24] | -$204.30 | [-$500.44, $121.32] |
| 2022 | openrule | halfway | stress | 5 | gross_prefunding | 63 | -$304.71 | [-$550.94, -$65.80] | -$270.72 | [-$557.80, $43.58] |
| 2022 | openrule | midpoint | base | 0 | assignment_cash_net | 63 | -$52.91 | [-$280.27, $182.37] | -$190.39 | [-$458.78, $110.28] |
| 2022 | openrule | midpoint | base | 0 | gross_prefunding | 63 | -$86.12 | [-$310.11, $145.76] | -$223.61 | [-$489.21, $75.14] |
| 2022 | openrule | midpoint | base | 1 | assignment_cash_net | 63 | -$80.22 | [-$311.60, $156.54] | -$200.11 | [-$471.41, $102.81] |
| 2022 | openrule | midpoint | base | 1 | gross_prefunding | 63 | -$113.43 | [-$340.93, $120.11] | -$233.32 | [-$501.56, $67.27] |
| 2022 | openrule | midpoint | base | 5 | assignment_cash_net | 63 | -$189.44 | [-$435.93, $53.58] | -$238.96 | [-$523.08, $74.98] |
| 2022 | openrule | midpoint | base | 5 | gross_prefunding | 63 | -$222.66 | [-$464.34, $17.62] | -$272.17 | [-$553.27, $37.20] |
| 2022 | openrule | midpoint | stress | 0 | assignment_cash_net | 63 | -$90.04 | [-$322.23, $146.44] | -$155.74 | [-$433.19, $152.78] |
| 2022 | openrule | midpoint | stress | 0 | gross_prefunding | 63 | -$156.46 | [-$381.12, $73.29] | -$222.16 | [-$491.97, $79.96] |
| 2022 | openrule | midpoint | stress | 1 | assignment_cash_net | 63 | -$117.35 | [-$352.95, $120.28] | -$165.45 | [-$446.00, $147.85] |
| 2022 | openrule | midpoint | stress | 1 | gross_prefunding | 63 | -$183.77 | [-$410.73, $48.23] | -$231.87 | [-$504.30, $72.28] |
| 2022 | openrule | midpoint | stress | 5 | assignment_cash_net | 63 | -$226.57 | [-$480.18, $19.06] | -$204.30 | [-$500.44, $121.32] |
| 2022 | openrule | midpoint | stress | 5 | gross_prefunding | 63 | -$293.00 | [-$539.50, -$53.61] | -$270.72 | [-$557.80, $43.58] |
| 2024 | assignmentoracle | full_cross | base | 0 | assignment_cash_net | 195 | $30.58 | [-$0.43, $60.11] | $506.95 | [$239.38, $791.53] |
| 2024 | assignmentoracle | full_cross | base | 0 | gross_prefunding | 195 | -$40.25 | [-$69.56, -$12.19] | $436.12 | [$171.97, $716.77] |
| 2024 | assignmentoracle | full_cross | base | 1 | assignment_cash_net | 195 | -$1.11 | [-$31.45, $28.09] | $506.99 | [$239.40, $791.61] |
| 2024 | assignmentoracle | full_cross | base | 1 | gross_prefunding | 195 | -$71.93 | [-$101.81, -$43.30] | $436.17 | [$171.99, $716.85] |
| 2024 | assignmentoracle | full_cross | base | 5 | assignment_cash_net | 195 | -$127.85 | [-$161.05, -$95.40] | $507.17 | [$239.47, $791.91] |
| 2024 | assignmentoracle | full_cross | base | 5 | gross_prefunding | 195 | -$198.68 | [-$234.82, -$163.71] | $436.35 | [$172.06, $717.14] |
| 2024 | assignmentoracle | full_cross | stress | 0 | assignment_cash_net | 195 | $17.87 | [-$13.03, $47.44] | $606.27 | [$333.43, $894.87] |
| 2024 | assignmentoracle | full_cross | stress | 0 | gross_prefunding | 195 | -$123.78 | [-$154.63, -$94.43] | $464.62 | [$198.99, $747.27] |
| 2024 | assignmentoracle | full_cross | stress | 1 | assignment_cash_net | 195 | -$13.81 | [-$44.16, $15.31] | $606.32 | [$333.45, $894.95] |
| 2024 | assignmentoracle | full_cross | stress | 1 | gross_prefunding | 195 | -$155.47 | [-$187.50, -$124.85] | $464.67 | [$199.01, $747.34] |
| 2024 | assignmentoracle | full_cross | stress | 5 | assignment_cash_net | 195 | -$140.56 | [-$173.86, -$108.00] | $606.50 | [$333.54, $895.24] |
| 2024 | assignmentoracle | full_cross | stress | 5 | gross_prefunding | 195 | -$282.21 | [-$323.27, -$242.30] | $464.84 | [$199.07, $747.64] |
| 2024 | assignmentoracle | halfway | base | 0 | assignment_cash_net | 195 | $40.89 | [$9.89, $70.53] | $506.95 | [$239.38, $791.53] |
| 2024 | assignmentoracle | halfway | base | 0 | gross_prefunding | 195 | -$29.94 | [-$59.24, -$1.79] | $436.12 | [$171.97, $716.77] |
| 2024 | assignmentoracle | halfway | base | 1 | assignment_cash_net | 195 | $9.20 | [-$21.32, $38.56] | $506.99 | [$239.40, $791.61] |
| 2024 | assignmentoracle | halfway | base | 1 | gross_prefunding | 195 | -$61.62 | [-$91.57, -$32.80] | $436.17 | [$171.99, $716.85] |
| 2024 | assignmentoracle | halfway | base | 5 | assignment_cash_net | 195 | -$117.54 | [-$150.82, -$85.04] | $507.17 | [$239.47, $791.91] |
| 2024 | assignmentoracle | halfway | base | 5 | gross_prefunding | 195 | -$188.37 | [-$224.70, -$153.11] | $436.35 | [$172.06, $717.14] |
| 2024 | assignmentoracle | halfway | stress | 0 | assignment_cash_net | 195 | $28.18 | [-$2.84, $57.78] | $606.27 | [$333.43, $894.87] |
| 2024 | assignmentoracle | halfway | stress | 0 | gross_prefunding | 195 | -$113.47 | [-$144.23, -$84.00] | $464.62 | [$198.99, $747.27] |
| 2024 | assignmentoracle | halfway | stress | 1 | assignment_cash_net | 195 | -$3.50 | [-$33.99, $25.83] | $606.32 | [$333.45, $894.95] |
| 2024 | assignmentoracle | halfway | stress | 1 | gross_prefunding | 195 | -$145.16 | [-$177.27, -$114.32] | $464.67 | [$199.01, $747.34] |
| 2024 | assignmentoracle | halfway | stress | 5 | assignment_cash_net | 195 | -$130.25 | [-$163.69, -$97.63] | $606.50 | [$333.54, $895.24] |
| 2024 | assignmentoracle | halfway | stress | 5 | gross_prefunding | 195 | -$271.90 | [-$313.03, -$231.94] | $464.84 | [$199.07, $747.64] |
| 2024 | assignmentoracle | midpoint | base | 0 | assignment_cash_net | 195 | $51.20 | [$19.99, $81.14] | $506.95 | [$239.38, $791.53] |
| 2024 | assignmentoracle | midpoint | base | 0 | gross_prefunding | 195 | -$19.63 | [-$49.11, $8.70] | $436.12 | [$171.97, $716.77] |
| 2024 | assignmentoracle | midpoint | base | 1 | assignment_cash_net | 195 | $19.51 | [-$11.05, $48.95] | $506.99 | [$239.40, $791.61] |
| 2024 | assignmentoracle | midpoint | base | 1 | gross_prefunding | 195 | -$51.32 | [-$81.34, -$22.33] | $436.17 | [$171.99, $716.85] |
| 2024 | assignmentoracle | midpoint | base | 5 | assignment_cash_net | 195 | -$107.23 | [-$140.65, -$74.70] | $507.17 | [$239.47, $791.91] |
| 2024 | assignmentoracle | midpoint | base | 5 | gross_prefunding | 195 | -$178.06 | [-$214.57, -$142.61] | $436.35 | [$172.06, $717.14] |
| 2024 | assignmentoracle | midpoint | stress | 0 | assignment_cash_net | 195 | $38.49 | [$7.44, $68.41] | $606.27 | [$333.43, $894.87] |
| 2024 | assignmentoracle | midpoint | stress | 0 | gross_prefunding | 195 | -$103.16 | [-$134.06, -$73.61] | $464.62 | [$198.99, $747.27] |
| 2024 | assignmentoracle | midpoint | stress | 1 | assignment_cash_net | 195 | $6.81 | [-$23.72, $36.22] | $606.32 | [$333.45, $894.95] |
| 2024 | assignmentoracle | midpoint | stress | 1 | gross_prefunding | 195 | -$134.85 | [-$167.05, -$103.76] | $464.67 | [$199.01, $747.34] |
| 2024 | assignmentoracle | midpoint | stress | 5 | assignment_cash_net | 195 | -$119.94 | [-$153.50, -$87.26] | $606.50 | [$333.54, $895.24] |
| 2024 | assignmentoracle | midpoint | stress | 5 | gross_prefunding | 195 | -$261.59 | [-$302.88, -$221.60] | $464.84 | [$199.07, $747.64] |
| 2024 | fixed1000 | full_cross | base | 0 | assignment_cash_net | 195 | $232.36 | [-$109.29, $512.80] | $708.73 | [$325.54, $1,073.76] |
| 2024 | fixed1000 | full_cross | base | 0 | gross_prefunding | 195 | $161.53 | [-$179.78, $444.22] | $637.90 | [$258.27, $1,000.95] |
| 2024 | fixed1000 | full_cross | base | 1 | assignment_cash_net | 195 | $155.85 | [-$184.80, $435.09] | $663.95 | [$277.82, $1,029.97] |
| 2024 | fixed1000 | full_cross | base | 1 | gross_prefunding | 195 | $85.02 | [-$255.05, $366.69] | $593.12 | [$211.41, $958.40] |
| 2024 | fixed1000 | full_cross | base | 5 | assignment_cash_net | 195 | -$150.20 | [-$490.78, $127.97] | $484.82 | [$83.79, $861.30] |
| 2024 | fixed1000 | full_cross | base | 5 | gross_prefunding | 195 | -$221.03 | [-$560.62, $57.57] | $413.99 | [$16.28, $787.00] |
| 2024 | fixed1000 | full_cross | stress | 0 | assignment_cash_net | 195 | $170.84 | [-$170.35, $450.23] | $759.24 | [$364.20, $1,129.19] |
| 2024 | fixed1000 | full_cross | stress | 0 | gross_prefunding | 195 | $29.19 | [-$311.74, $312.18] | $617.59 | [$233.00, $983.71] |
| 2024 | fixed1000 | full_cross | stress | 1 | assignment_cash_net | 195 | $94.33 | [-$246.27, $373.38] | $714.46 | [$315.77, $1,089.52] |
| 2024 | fixed1000 | full_cross | stress | 1 | gross_prefunding | 195 | -$47.33 | [-$387.31, $234.22] | $572.81 | [$185.21, $939.82] |
| 2024 | fixed1000 | full_cross | stress | 5 | assignment_cash_net | 195 | -$211.72 | [-$555.56, $65.87] | $535.33 | [$126.44, $922.60] |
| 2024 | fixed1000 | full_cross | stress | 5 | gross_prefunding | 195 | -$353.38 | [-$693.79, -$74.61] | $393.68 | [-$10.00, $771.57] |
| 2024 | fixed1000 | halfway | base | 0 | assignment_cash_net | 195 | $242.67 | [-$98.45, $523.41] | $708.73 | [$325.54, $1,073.76] |
| 2024 | fixed1000 | halfway | base | 0 | gross_prefunding | 195 | $171.84 | [-$168.98, $454.63] | $637.90 | [$258.27, $1,000.95] |
| 2024 | fixed1000 | halfway | base | 1 | assignment_cash_net | 195 | $166.15 | [-$174.22, $445.58] | $663.95 | [$277.82, $1,029.97] |
| 2024 | fixed1000 | halfway | base | 1 | gross_prefunding | 195 | $95.33 | [-$244.90, $376.71] | $593.12 | [$211.41, $958.40] |
| 2024 | fixed1000 | halfway | base | 5 | assignment_cash_net | 195 | -$139.90 | [-$480.35, $138.43] | $484.82 | [$83.79, $861.30] |
| 2024 | fixed1000 | halfway | base | 5 | gross_prefunding | 195 | -$210.72 | [-$550.54, $67.87] | $413.99 | [$16.28, $787.00] |
| 2024 | fixed1000 | halfway | stress | 0 | assignment_cash_net | 195 | $181.15 | [-$160.13, $460.15] | $759.24 | [$364.20, $1,129.19] |
| 2024 | fixed1000 | halfway | stress | 0 | gross_prefunding | 195 | $39.50 | [-$301.81, $322.15] | $617.59 | [$233.00, $983.71] |
| 2024 | fixed1000 | halfway | stress | 1 | assignment_cash_net | 195 | $104.64 | [-$236.17, $383.64] | $714.46 | [$315.77, $1,089.52] |
| 2024 | fixed1000 | halfway | stress | 1 | gross_prefunding | 195 | -$37.02 | [-$377.35, $244.55] | $572.81 | [$185.21, $939.82] |
| 2024 | fixed1000 | halfway | stress | 5 | assignment_cash_net | 195 | -$201.41 | [-$545.62, $76.48] | $535.33 | [$126.44, $922.60] |
| 2024 | fixed1000 | halfway | stress | 5 | gross_prefunding | 195 | -$343.07 | [-$683.17, -$64.04] | $393.68 | [-$10.00, $771.57] |
| 2024 | fixed1000 | midpoint | base | 0 | assignment_cash_net | 195 | $252.98 | [-$87.75, $533.99] | $708.73 | [$325.54, $1,073.76] |
| 2024 | fixed1000 | midpoint | base | 0 | gross_prefunding | 195 | $182.15 | [-$159.05, $465.17] | $637.90 | [$258.27, $1,000.95] |
| 2024 | fixed1000 | midpoint | base | 1 | assignment_cash_net | 195 | $176.46 | [-$163.65, $456.32] | $663.95 | [$277.82, $1,029.97] |
| 2024 | fixed1000 | midpoint | base | 1 | gross_prefunding | 195 | $105.64 | [-$234.72, $387.39] | $593.12 | [$211.41, $958.40] |
| 2024 | fixed1000 | midpoint | base | 5 | assignment_cash_net | 195 | -$129.59 | [-$470.17, $148.71] | $484.82 | [$83.79, $861.30] |
| 2024 | fixed1000 | midpoint | base | 5 | gross_prefunding | 195 | -$200.41 | [-$539.91, $78.48] | $413.99 | [$16.28, $787.00] |
| 2024 | fixed1000 | midpoint | stress | 0 | assignment_cash_net | 195 | $191.46 | [-$149.16, $470.79] | $759.24 | [$364.20, $1,129.19] |
| 2024 | fixed1000 | midpoint | stress | 0 | gross_prefunding | 195 | $49.81 | [-$291.23, $332.45] | $617.59 | [$233.00, $983.71] |
| 2024 | fixed1000 | midpoint | stress | 1 | assignment_cash_net | 195 | $114.95 | [-$226.06, $394.18] | $714.46 | [$315.77, $1,089.52] |
| 2024 | fixed1000 | midpoint | stress | 1 | gross_prefunding | 195 | -$26.71 | [-$367.42, $255.05] | $572.81 | [$185.21, $939.82] |
| 2024 | fixed1000 | midpoint | stress | 5 | assignment_cash_net | 195 | -$191.10 | [-$535.36, $87.20] | $535.33 | [$126.44, $922.60] |
| 2024 | fixed1000 | midpoint | stress | 5 | gross_prefunding | 195 | -$332.76 | [-$672.98, -$53.43] | $393.68 | [-$10.00, $771.57] |
| 2024 | fixed500 | full_cross | base | 0 | assignment_cash_net | 195 | -$121.80 | [-$356.85, $98.56] | $354.57 | [$162.98, $537.11] |
| 2024 | fixed500 | full_cross | base | 0 | gross_prefunding | 195 | -$157.42 | [-$393.15, $64.39] | $318.95 | [$129.14, $500.47] |
| 2024 | fixed500 | full_cross | base | 1 | assignment_cash_net | 195 | -$175.92 | [-$411.01, $44.06] | $332.18 | [$139.12, $515.25] |
| 2024 | fixed500 | full_cross | base | 1 | gross_prefunding | 195 | -$211.54 | [-$447.40, $10.25] | $296.56 | [$105.71, $479.20] |
| 2024 | fixed500 | full_cross | base | 5 | assignment_cash_net | 195 | -$392.40 | [-$627.66, -$171.94] | $242.62 | [$42.08, $430.87] |
| 2024 | fixed500 | full_cross | base | 5 | gross_prefunding | 195 | -$428.03 | [-$664.45, -$206.12] | $207.00 | [$8.14, $393.50] |
| 2024 | fixed500 | full_cross | stress | 0 | assignment_cash_net | 195 | -$208.36 | [-$443.83, $12.46] | $380.04 | [$182.47, $565.03] |
| 2024 | fixed500 | full_cross | stress | 0 | gross_prefunding | 195 | -$279.61 | [-$516.20, -$55.85] | $308.79 | [$116.50, $491.85] |
| 2024 | fixed500 | full_cross | stress | 1 | assignment_cash_net | 195 | -$262.49 | [-$497.77, -$41.71] | $357.65 | [$158.25, $545.23] |
| 2024 | fixed500 | full_cross | stress | 1 | gross_prefunding | 195 | -$333.73 | [-$570.32, -$110.02] | $286.40 | [$92.61, $469.91] |
| 2024 | fixed500 | full_cross | stress | 5 | assignment_cash_net | 195 | -$478.97 | [-$714.66, -$258.16] | $268.08 | [$63.63, $461.73] |
| 2024 | fixed500 | full_cross | stress | 5 | gross_prefunding | 195 | -$550.22 | [-$786.90, -$327.12] | $196.84 | [-$5.00, $385.79] |
| 2024 | fixed500 | halfway | base | 0 | assignment_cash_net | 195 | -$111.49 | [-$346.20, $108.75] | $354.57 | [$162.98, $537.11] |
| 2024 | fixed500 | halfway | base | 0 | gross_prefunding | 195 | -$147.11 | [-$382.84, $74.73] | $318.95 | [$129.14, $500.47] |
| 2024 | fixed500 | halfway | base | 1 | assignment_cash_net | 195 | -$165.61 | [-$400.57, $54.48] | $332.18 | [$139.12, $515.25] |
| 2024 | fixed500 | halfway | base | 1 | gross_prefunding | 195 | -$201.23 | [-$437.17, $20.42] | $296.56 | [$105.71, $479.20] |
| 2024 | fixed500 | halfway | base | 5 | assignment_cash_net | 195 | -$382.09 | [-$617.58, -$161.50] | $242.62 | [$42.08, $430.87] |
| 2024 | fixed500 | halfway | base | 5 | gross_prefunding | 195 | -$417.72 | [-$654.31, -$195.90] | $207.00 | [$8.14, $393.50] |
| 2024 | fixed500 | halfway | stress | 0 | assignment_cash_net | 195 | -$198.05 | [-$433.35, $22.78] | $380.04 | [$182.47, $565.03] |
| 2024 | fixed500 | halfway | stress | 0 | gross_prefunding | 195 | -$269.30 | [-$505.72, -$45.48] | $308.79 | [$116.50, $491.85] |
| 2024 | fixed500 | halfway | stress | 1 | assignment_cash_net | 195 | -$252.18 | [-$487.53, -$31.49] | $357.65 | [$158.25, $545.23] |
| 2024 | fixed500 | halfway | stress | 1 | gross_prefunding | 195 | -$323.42 | [-$560.01, -$99.63] | $286.40 | [$92.61, $469.91] |
| 2024 | fixed500 | halfway | stress | 5 | assignment_cash_net | 195 | -$468.66 | [-$704.57, -$247.70] | $268.08 | [$63.63, $461.73] |
| 2024 | fixed500 | halfway | stress | 5 | gross_prefunding | 195 | -$539.90 | [-$776.86, -$316.57] | $196.84 | [-$5.00, $385.79] |
| 2024 | fixed500 | midpoint | base | 0 | assignment_cash_net | 195 | -$101.18 | [-$335.46, $118.89] | $354.57 | [$162.98, $537.11] |
| 2024 | fixed500 | midpoint | base | 0 | gross_prefunding | 195 | -$136.80 | [-$373.05, $85.35] | $318.95 | [$129.14, $500.47] |
| 2024 | fixed500 | midpoint | base | 1 | assignment_cash_net | 195 | -$155.30 | [-$389.72, $64.76] | $332.18 | [$139.12, $515.25] |
| 2024 | fixed500 | midpoint | base | 1 | gross_prefunding | 195 | -$190.92 | [-$426.92, $30.58] | $296.56 | [$105.71, $479.20] |
| 2024 | fixed500 | midpoint | base | 5 | assignment_cash_net | 195 | -$371.79 | [-$607.23, -$151.39] | $242.62 | [$42.08, $430.87] |
| 2024 | fixed500 | midpoint | base | 5 | gross_prefunding | 195 | -$407.41 | [-$644.14, -$185.74] | $207.00 | [$8.14, $393.50] |
| 2024 | fixed500 | midpoint | stress | 0 | assignment_cash_net | 195 | -$187.74 | [-$423.15, $32.90] | $380.04 | [$182.47, $565.03] |
| 2024 | fixed500 | midpoint | stress | 0 | gross_prefunding | 195 | -$258.99 | [-$495.79, -$35.36] | $308.79 | [$116.50, $491.85] |
| 2024 | fixed500 | midpoint | stress | 1 | assignment_cash_net | 195 | -$241.87 | [-$477.36, -$21.14] | $357.65 | [$158.25, $545.23] |
| 2024 | fixed500 | midpoint | stress | 1 | gross_prefunding | 195 | -$313.11 | [-$549.75, -$89.12] | $286.40 | [$92.61, $469.91] |
| 2024 | fixed500 | midpoint | stress | 5 | assignment_cash_net | 195 | -$458.35 | [-$694.37, -$237.68] | $268.08 | [$63.63, $461.73] |
| 2024 | fixed500 | midpoint | stress | 5 | gross_prefunding | 195 | -$529.59 | [-$766.59, -$306.32] | $196.84 | [-$5.00, $385.79] |
| 2024 | openrule | full_cross | base | 0 | assignment_cash_net | 195 | $13.54 | [-$177.16, $204.14] | $489.91 | [$201.81, $790.08] |
| 2024 | openrule | full_cross | base | 0 | gross_prefunding | 195 | -$43.41 | [-$233.38, $146.35] | $432.96 | [$146.33, $730.40] |
| 2024 | openrule | full_cross | base | 1 | assignment_cash_net | 195 | -$33.08 | [-$223.26, $158.09] | $475.02 | [$187.66, $774.38] |
| 2024 | openrule | full_cross | base | 1 | gross_prefunding | 195 | -$90.03 | [-$279.89, $99.65] | $418.07 | [$132.92, $714.32] |
| 2024 | openrule | full_cross | base | 5 | assignment_cash_net | 195 | -$219.52 | [-$409.22, -$27.72] | $415.50 | [$128.88, $713.77] |
| 2024 | openrule | full_cross | base | 5 | gross_prefunding | 195 | -$276.47 | [-$466.23, -$86.14] | $358.55 | [$74.59, $653.01] |
| 2024 | openrule | full_cross | stress | 0 | assignment_cash_net | 195 | -$33.64 | [-$226.74, $159.10] | $554.77 | [$262.78, $859.28] |
| 2024 | openrule | full_cross | stress | 0 | gross_prefunding | 195 | -$147.54 | [-$338.15, $41.86] | $440.87 | [$154.89, $738.52] |
| 2024 | openrule | full_cross | stress | 1 | assignment_cash_net | 195 | -$80.25 | [-$271.93, $112.98] | $539.89 | [$247.10, $843.81] |
| 2024 | openrule | full_cross | stress | 1 | gross_prefunding | 195 | -$194.15 | [-$385.73, -$4.40] | $425.99 | [$140.58, $722.37] |
| 2024 | openrule | full_cross | stress | 5 | assignment_cash_net | 195 | -$266.69 | [-$458.02, -$73.75] | $480.36 | [$185.95, $782.21] |
| 2024 | openrule | full_cross | stress | 5 | gross_prefunding | 195 | -$380.59 | [-$571.65, -$187.91] | $366.46 | [$81.13, $663.53] |
| 2024 | openrule | halfway | base | 0 | assignment_cash_net | 195 | $23.84 | [-$166.98, $214.58] | $489.91 | [$201.81, $790.08] |
| 2024 | openrule | halfway | base | 0 | gross_prefunding | 195 | -$33.11 | [-$223.31, $156.68] | $432.96 | [$146.33, $730.40] |
| 2024 | openrule | halfway | base | 1 | assignment_cash_net | 195 | -$22.77 | [-$213.29, $168.79] | $475.02 | [$187.66, $774.38] |
| 2024 | openrule | halfway | base | 1 | gross_prefunding | 195 | -$79.72 | [-$269.94, $110.31] | $418.07 | [$132.92, $714.32] |
| 2024 | openrule | halfway | base | 5 | assignment_cash_net | 195 | -$209.21 | [-$398.91, -$17.09] | $415.50 | [$128.88, $713.77] |
| 2024 | openrule | halfway | base | 5 | gross_prefunding | 195 | -$266.16 | [-$455.79, -$75.70] | $358.55 | [$74.59, $653.01] |
| 2024 | openrule | halfway | stress | 0 | assignment_cash_net | 195 | -$23.33 | [-$216.56, $169.37] | $554.77 | [$262.78, $859.28] |
| 2024 | openrule | halfway | stress | 0 | gross_prefunding | 195 | -$137.23 | [-$328.38, $52.57] | $440.87 | [$154.89, $738.52] |
| 2024 | openrule | halfway | stress | 1 | assignment_cash_net | 195 | -$69.94 | [-$261.84, $123.74] | $539.89 | [$247.10, $843.81] |
| 2024 | openrule | halfway | stress | 1 | gross_prefunding | 195 | -$183.84 | [-$375.93, $6.04] | $425.99 | [$140.58, $722.37] |
| 2024 | openrule | halfway | stress | 5 | assignment_cash_net | 195 | -$256.38 | [-$447.72, -$63.01] | $480.36 | [$185.95, $782.21] |
| 2024 | openrule | halfway | stress | 5 | gross_prefunding | 195 | -$370.28 | [-$561.65, -$177.10] | $366.46 | [$81.13, $663.53] |
| 2024 | openrule | midpoint | base | 0 | assignment_cash_net | 195 | $34.15 | [-$156.56, $225.08] | $489.91 | [$201.81, $790.08] |
| 2024 | openrule | midpoint | base | 0 | gross_prefunding | 195 | -$22.80 | [-$212.89, $167.29] | $432.96 | [$146.33, $730.40] |
| 2024 | openrule | midpoint | base | 1 | assignment_cash_net | 195 | -$12.46 | [-$203.13, $179.07] | $475.02 | [$187.66, $774.38] |
| 2024 | openrule | midpoint | base | 1 | gross_prefunding | 195 | -$69.41 | [-$259.45, $120.92] | $418.07 | [$132.92, $714.32] |
| 2024 | openrule | midpoint | base | 5 | assignment_cash_net | 195 | -$198.90 | [-$388.85, -$6.97] | $415.50 | [$128.88, $713.77] |
| 2024 | openrule | midpoint | base | 5 | gross_prefunding | 195 | -$255.85 | [-$445.69, -$65.33] | $358.55 | [$74.59, $653.01] |
| 2024 | openrule | midpoint | stress | 0 | assignment_cash_net | 195 | -$13.02 | [-$206.41, $179.77] | $554.77 | [$262.78, $859.28] |
| 2024 | openrule | midpoint | stress | 0 | gross_prefunding | 195 | -$126.92 | [-$318.56, $63.39] | $440.87 | [$154.89, $738.52] |
| 2024 | openrule | midpoint | stress | 1 | assignment_cash_net | 195 | -$59.63 | [-$252.07, $134.46] | $539.89 | [$247.10, $843.81] |
| 2024 | openrule | midpoint | stress | 1 | gross_prefunding | 195 | -$173.53 | [-$365.73, $16.82] | $425.99 | [$140.58, $722.37] |
| 2024 | openrule | midpoint | stress | 5 | assignment_cash_net | 195 | -$246.07 | [-$437.58, -$52.18] | $480.36 | [$185.95, $782.21] |
| 2024 | openrule | midpoint | stress | 5 | gross_prefunding | 195 | -$359.97 | [-$551.14, -$166.77] | $366.46 | [$81.13, $663.53] |
| 2025 (Jan-Aug) | assignmentoracle | full_cross | base | 0 | assignment_cash_net | 127 | $7.99 | [-$116.32, $93.80] | -$216.28 | [-$856.27, $377.11] |
| 2025 (Jan-Aug) | assignmentoracle | full_cross | base | 0 | gross_prefunding | 127 | -$58.63 | [-$182.49, $27.82] | -$282.91 | [-$920.18, $305.31] |
| 2025 (Jan-Aug) | assignmentoracle | full_cross | base | 1 | assignment_cash_net | 127 | -$24.33 | [-$147.51, $60.50] | -$216.30 | [-$856.36, $377.14] |
| 2025 (Jan-Aug) | assignmentoracle | full_cross | base | 1 | gross_prefunding | 127 | -$90.96 | [-$214.95, -$4.56] | -$282.93 | [-$920.27, $305.34] |
| 2025 (Jan-Aug) | assignmentoracle | full_cross | base | 5 | assignment_cash_net | 127 | -$153.65 | [-$276.06, -$66.52] | -$216.40 | [-$856.72, $377.27] |
| 2025 (Jan-Aug) | assignmentoracle | full_cross | base | 5 | gross_prefunding | 127 | -$220.28 | [-$344.73, -$129.06] | -$283.03 | [-$920.63, $305.48] |
| 2025 (Jan-Aug) | assignmentoracle | full_cross | stress | 0 | assignment_cash_net | 127 | -$4.66 | [-$128.90, $81.07] | -$122.77 | [-$767.69, $478.51] |
| 2025 (Jan-Aug) | assignmentoracle | full_cross | stress | 0 | gross_prefunding | 127 | -$137.92 | [-$264.04, -$47.52] | -$256.02 | [-$894.16, $333.81] |
| 2025 (Jan-Aug) | assignmentoracle | full_cross | stress | 1 | assignment_cash_net | 127 | -$36.99 | [-$160.33, $47.98] | -$122.79 | [-$767.78, $478.54] |
| 2025 (Jan-Aug) | assignmentoracle | full_cross | stress | 1 | gross_prefunding | 127 | -$170.25 | [-$296.24, -$78.89] | -$256.05 | [-$894.25, $333.84] |
| 2025 (Jan-Aug) | assignmentoracle | full_cross | stress | 5 | assignment_cash_net | 127 | -$166.31 | [-$288.99, -$79.21] | -$122.89 | [-$768.14, $478.68] |
| 2025 (Jan-Aug) | assignmentoracle | full_cross | stress | 5 | gross_prefunding | 127 | -$299.57 | [-$427.25, -$201.11] | -$256.15 | [-$894.61, $333.97] |
| 2025 (Jan-Aug) | assignmentoracle | halfway | base | 0 | assignment_cash_net | 127 | $20.30 | [-$102.24, $105.48] | -$216.28 | [-$856.27, $377.11] |
| 2025 (Jan-Aug) | assignmentoracle | halfway | base | 0 | gross_prefunding | 127 | -$46.33 | [-$168.67, $39.60] | -$282.91 | [-$920.18, $305.31] |
| 2025 (Jan-Aug) | assignmentoracle | halfway | base | 1 | assignment_cash_net | 127 | -$12.03 | [-$133.71, $72.53] | -$216.30 | [-$856.36, $377.14] |
| 2025 (Jan-Aug) | assignmentoracle | halfway | base | 1 | gross_prefunding | 127 | -$78.66 | [-$201.14, $7.13] | -$282.93 | [-$920.27, $305.34] |
| 2025 (Jan-Aug) | assignmentoracle | halfway | base | 5 | assignment_cash_net | 127 | -$141.35 | [-$261.86, -$54.93] | -$216.40 | [-$856.72, $377.27] |
| 2025 (Jan-Aug) | assignmentoracle | halfway | base | 5 | gross_prefunding | 127 | -$207.98 | [-$330.65, -$117.34] | -$283.03 | [-$920.63, $305.48] |
| 2025 (Jan-Aug) | assignmentoracle | halfway | stress | 0 | assignment_cash_net | 127 | $7.65 | [-$115.02, $92.93] | -$122.77 | [-$767.69, $478.51] |
| 2025 (Jan-Aug) | assignmentoracle | halfway | stress | 0 | gross_prefunding | 127 | -$125.61 | [-$250.03, -$36.02] | -$256.02 | [-$894.16, $333.81] |
| 2025 (Jan-Aug) | assignmentoracle | halfway | stress | 1 | assignment_cash_net | 127 | -$24.68 | [-$146.29, $59.87] | -$122.79 | [-$767.78, $478.54] |
| 2025 (Jan-Aug) | assignmentoracle | halfway | stress | 1 | gross_prefunding | 127 | -$157.94 | [-$282.15, -$67.25] | -$256.05 | [-$894.25, $333.84] |
| 2025 (Jan-Aug) | assignmentoracle | halfway | stress | 5 | assignment_cash_net | 127 | -$154.00 | [-$274.81, -$67.27] | -$122.89 | [-$768.14, $478.68] |
| 2025 (Jan-Aug) | assignmentoracle | halfway | stress | 5 | gross_prefunding | 127 | -$287.26 | [-$413.04, -$189.58] | -$256.15 | [-$894.61, $333.97] |
| 2025 (Jan-Aug) | assignmentoracle | midpoint | base | 0 | assignment_cash_net | 127 | $32.60 | [-$88.25, $117.28] | -$216.28 | [-$856.27, $377.11] |
| 2025 (Jan-Aug) | assignmentoracle | midpoint | base | 0 | gross_prefunding | 127 | -$34.03 | [-$155.07, $51.25] | -$282.91 | [-$920.18, $305.31] |
| 2025 (Jan-Aug) | assignmentoracle | midpoint | base | 1 | assignment_cash_net | 127 | $0.27 | [-$119.52, $84.43] | -$216.30 | [-$856.36, $377.14] |
| 2025 (Jan-Aug) | assignmentoracle | midpoint | base | 1 | gross_prefunding | 127 | -$66.36 | [-$187.30, $18.78] | -$282.93 | [-$920.27, $305.34] |
| 2025 (Jan-Aug) | assignmentoracle | midpoint | base | 5 | assignment_cash_net | 127 | -$129.05 | [-$247.82, -$43.37] | -$216.40 | [-$856.72, $377.27] |
| 2025 (Jan-Aug) | assignmentoracle | midpoint | base | 5 | gross_prefunding | 127 | -$195.68 | [-$316.74, -$105.70] | -$283.03 | [-$920.63, $305.48] |
| 2025 (Jan-Aug) | assignmentoracle | midpoint | stress | 0 | assignment_cash_net | 127 | $19.95 | [-$100.84, $104.74] | -$122.77 | [-$767.69, $478.51] |
| 2025 (Jan-Aug) | assignmentoracle | midpoint | stress | 0 | gross_prefunding | 127 | -$113.31 | [-$235.97, -$24.47] | -$256.02 | [-$894.16, $333.81] |
| 2025 (Jan-Aug) | assignmentoracle | midpoint | stress | 1 | assignment_cash_net | 127 | -$12.38 | [-$132.19, $71.77] | -$122.79 | [-$767.78, $478.54] |
| 2025 (Jan-Aug) | assignmentoracle | midpoint | stress | 1 | gross_prefunding | 127 | -$145.64 | [-$268.12, -$55.69] | -$256.05 | [-$894.25, $333.84] |
| 2025 (Jan-Aug) | assignmentoracle | midpoint | stress | 5 | assignment_cash_net | 127 | -$141.70 | [-$260.71, -$55.73] | -$122.89 | [-$768.14, $478.68] |
| 2025 (Jan-Aug) | assignmentoracle | midpoint | stress | 5 | gross_prefunding | 127 | -$274.96 | [-$398.41, -$177.95] | -$256.15 | [-$894.61, $333.97] |
| 2025 (Jan-Aug) | fixed1000 | full_cross | base | 0 | assignment_cash_net | 127 | $47.48 | [-$653.35, $675.71] | -$176.79 | [-$1,419.31, $871.50] |
| 2025 (Jan-Aug) | fixed1000 | full_cross | base | 0 | gross_prefunding | 127 | -$19.15 | [-$717.48, $609.99] | -$243.42 | [-$1,476.07, $803.93] |
| 2025 (Jan-Aug) | fixed1000 | full_cross | base | 1 | assignment_cash_net | 127 | -$38.91 | [-$739.15, $588.65] | -$230.88 | [-$1,472.82, $816.22] |
| 2025 (Jan-Aug) | fixed1000 | full_cross | base | 1 | gross_prefunding | 127 | -$105.54 | [-$801.90, $522.20] | -$297.50 | [-$1,536.13, $748.57] |
| 2025 (Jan-Aug) | fixed1000 | full_cross | base | 5 | assignment_cash_net | 127 | -$384.47 | [-$1,080.12, $244.70] | -$447.22 | [-$1,692.63, $605.48] |
| 2025 (Jan-Aug) | fixed1000 | full_cross | base | 5 | gross_prefunding | 127 | -$451.10 | [-$1,146.93, $175.49] | -$513.85 | [-$1,755.83, $535.11] |
| 2025 (Jan-Aug) | fixed1000 | full_cross | stress | 0 | assignment_cash_net | 127 | -$29.16 | [-$730.68, $600.44] | -$147.27 | [-$1,394.80, $904.95] |
| 2025 (Jan-Aug) | fixed1000 | full_cross | stress | 0 | gross_prefunding | 127 | -$162.42 | [-$859.93, $465.44] | -$280.53 | [-$1,522.38, $767.99] |
| 2025 (Jan-Aug) | fixed1000 | full_cross | stress | 1 | assignment_cash_net | 127 | -$115.55 | [-$816.37, $513.91] | -$201.36 | [-$1,450.34, $854.17] |
| 2025 (Jan-Aug) | fixed1000 | full_cross | stress | 1 | gross_prefunding | 127 | -$248.81 | [-$944.74, $380.80] | -$334.61 | [-$1,576.69, $711.84] |
| 2025 (Jan-Aug) | fixed1000 | full_cross | stress | 5 | assignment_cash_net | 127 | -$461.12 | [-$1,159.93, $167.45] | -$417.70 | [-$1,667.09, $644.19] |
| 2025 (Jan-Aug) | fixed1000 | full_cross | stress | 5 | gross_prefunding | 127 | -$594.37 | [-$1,289.55, $32.76] | -$550.96 | [-$1,797.49, $502.77] |
| 2025 (Jan-Aug) | fixed1000 | halfway | base | 0 | assignment_cash_net | 127 | $59.79 | [-$640.10, $687.20] | -$176.79 | [-$1,419.31, $871.50] |
| 2025 (Jan-Aug) | fixed1000 | halfway | base | 0 | gross_prefunding | 127 | -$6.84 | [-$704.15, $621.91] | -$243.42 | [-$1,476.07, $803.93] |
| 2025 (Jan-Aug) | fixed1000 | halfway | base | 1 | assignment_cash_net | 127 | -$26.60 | [-$725.74, $600.63] | -$230.88 | [-$1,472.82, $816.22] |
| 2025 (Jan-Aug) | fixed1000 | halfway | base | 1 | gross_prefunding | 127 | -$93.23 | [-$789.43, $533.54] | -$297.50 | [-$1,536.13, $748.57] |
| 2025 (Jan-Aug) | fixed1000 | halfway | base | 5 | assignment_cash_net | 127 | -$372.17 | [-$1,067.67, $256.03] | -$447.22 | [-$1,692.63, $605.48] |
| 2025 (Jan-Aug) | fixed1000 | halfway | base | 5 | gross_prefunding | 127 | -$438.80 | [-$1,134.14, $187.01] | -$513.85 | [-$1,755.83, $535.11] |
| 2025 (Jan-Aug) | fixed1000 | halfway | stress | 0 | assignment_cash_net | 127 | -$16.86 | [-$717.40, $612.02] | -$147.27 | [-$1,394.80, $904.95] |
| 2025 (Jan-Aug) | fixed1000 | halfway | stress | 0 | gross_prefunding | 127 | -$150.12 | [-$846.47, $476.76] | -$280.53 | [-$1,522.38, $767.99] |
| 2025 (Jan-Aug) | fixed1000 | halfway | stress | 1 | assignment_cash_net | 127 | -$103.25 | [-$803.24, $525.93] | -$201.36 | [-$1,450.34, $854.17] |
| 2025 (Jan-Aug) | fixed1000 | halfway | stress | 1 | gross_prefunding | 127 | -$236.51 | [-$932.64, $391.96] | -$334.61 | [-$1,576.69, $711.84] |
| 2025 (Jan-Aug) | fixed1000 | halfway | stress | 5 | assignment_cash_net | 127 | -$448.81 | [-$1,148.16, $178.81] | -$417.70 | [-$1,667.09, $644.19] |
| 2025 (Jan-Aug) | fixed1000 | halfway | stress | 5 | gross_prefunding | 127 | -$582.07 | [-$1,276.48, $43.72] | -$550.96 | [-$1,797.49, $502.77] |
| 2025 (Jan-Aug) | fixed1000 | midpoint | base | 0 | assignment_cash_net | 127 | $72.09 | [-$626.76, $698.67] | -$176.79 | [-$1,419.31, $871.50] |
| 2025 (Jan-Aug) | fixed1000 | midpoint | base | 0 | gross_prefunding | 127 | $5.46 | [-$690.88, $633.60] | -$243.42 | [-$1,476.07, $803.93] |
| 2025 (Jan-Aug) | fixed1000 | midpoint | base | 1 | assignment_cash_net | 127 | -$14.30 | [-$712.61, $612.63] | -$230.88 | [-$1,472.82, $816.22] |
| 2025 (Jan-Aug) | fixed1000 | midpoint | base | 1 | gross_prefunding | 127 | -$80.93 | [-$776.54, $545.04] | -$297.50 | [-$1,536.13, $748.57] |
| 2025 (Jan-Aug) | fixed1000 | midpoint | base | 5 | assignment_cash_net | 127 | -$359.86 | [-$1,055.40, $267.93] | -$447.22 | [-$1,692.63, $605.48] |
| 2025 (Jan-Aug) | fixed1000 | midpoint | base | 5 | gross_prefunding | 127 | -$426.49 | [-$1,120.85, $199.44] | -$513.85 | [-$1,755.83, $535.11] |
| 2025 (Jan-Aug) | fixed1000 | midpoint | stress | 0 | assignment_cash_net | 127 | -$4.55 | [-$705.49, $623.86] | -$147.27 | [-$1,394.80, $904.95] |
| 2025 (Jan-Aug) | fixed1000 | midpoint | stress | 0 | gross_prefunding | 127 | -$137.81 | [-$833.93, $487.97] | -$280.53 | [-$1,522.38, $767.99] |
| 2025 (Jan-Aug) | fixed1000 | midpoint | stress | 1 | assignment_cash_net | 127 | -$90.94 | [-$790.09, $537.88] | -$201.36 | [-$1,450.34, $854.17] |
| 2025 (Jan-Aug) | fixed1000 | midpoint | stress | 1 | gross_prefunding | 127 | -$224.20 | [-$919.58, $403.12] | -$334.61 | [-$1,576.69, $711.84] |
| 2025 (Jan-Aug) | fixed1000 | midpoint | stress | 5 | assignment_cash_net | 127 | -$436.51 | [-$1,134.36, $190.18] | -$417.70 | [-$1,667.09, $644.19] |
| 2025 (Jan-Aug) | fixed1000 | midpoint | stress | 5 | gross_prefunding | 127 | -$569.76 | [-$1,263.93, $55.79] | -$550.96 | [-$1,797.49, $502.77] |
| 2025 (Jan-Aug) | fixed500 | full_cross | base | 0 | assignment_cash_net | 127 | $136.16 | [-$185.50, $447.72] | -$88.11 | [-$709.34, $436.04] |
| 2025 (Jan-Aug) | fixed500 | full_cross | base | 0 | gross_prefunding | 127 | $102.56 | [-$219.67, $416.09] | -$121.71 | [-$738.03, $401.96] |
| 2025 (Jan-Aug) | fixed500 | full_cross | base | 1 | assignment_cash_net | 127 | $76.82 | [-$244.88, $388.46] | -$115.15 | [-$736.15, $408.42] |
| 2025 (Jan-Aug) | fixed500 | full_cross | base | 1 | gross_prefunding | 127 | $43.21 | [-$279.14, $356.71] | -$148.75 | [-$768.07, $374.28] |
| 2025 (Jan-Aug) | fixed500 | full_cross | base | 5 | assignment_cash_net | 127 | -$160.57 | [-$480.13, $151.44] | -$223.32 | [-$846.07, $303.01] |
| 2025 (Jan-Aug) | fixed500 | full_cross | base | 5 | gross_prefunding | 127 | -$194.18 | [-$516.60, $118.63] | -$256.92 | [-$877.91, $267.55] |
| 2025 (Jan-Aug) | fixed500 | full_cross | stress | 0 | assignment_cash_net | 127 | $45.05 | [-$277.11, $357.64] | -$73.06 | [-$696.88, $452.98] |
| 2025 (Jan-Aug) | fixed500 | full_cross | stress | 0 | gross_prefunding | 127 | -$22.16 | [-$348.78, $294.29] | -$140.26 | [-$761.19, $383.99] |
| 2025 (Jan-Aug) | fixed500 | full_cross | stress | 1 | assignment_cash_net | 127 | -$14.30 | [-$336.14, $298.42] | -$100.10 | [-$724.67, $427.86] |
| 2025 (Jan-Aug) | fixed500 | full_cross | stress | 1 | gross_prefunding | 127 | -$81.51 | [-$407.84, $234.76] | -$167.31 | [-$788.34, $355.92] |
| 2025 (Jan-Aug) | fixed500 | full_cross | stress | 5 | assignment_cash_net | 127 | -$251.69 | [-$572.33, $60.17] | -$208.28 | [-$833.10, $322.71] |
| 2025 (Jan-Aug) | fixed500 | full_cross | stress | 5 | gross_prefunding | 127 | -$318.89 | [-$645.33, -$3.05] | -$275.48 | [-$898.75, $251.39] |
| 2025 (Jan-Aug) | fixed500 | halfway | base | 0 | assignment_cash_net | 127 | $148.47 | [-$172.10, $459.62] | -$88.11 | [-$709.34, $436.04] |
| 2025 (Jan-Aug) | fixed500 | halfway | base | 0 | gross_prefunding | 127 | $114.87 | [-$206.83, $428.14] | -$121.71 | [-$738.03, $401.96] |
| 2025 (Jan-Aug) | fixed500 | halfway | base | 1 | assignment_cash_net | 127 | $89.12 | [-$230.56, $400.50] | -$115.15 | [-$736.15, $408.42] |
| 2025 (Jan-Aug) | fixed500 | halfway | base | 1 | gross_prefunding | 127 | $55.52 | [-$266.25, $368.76] | -$148.75 | [-$768.07, $374.28] |
| 2025 (Jan-Aug) | fixed500 | halfway | base | 5 | assignment_cash_net | 127 | -$148.27 | [-$467.18, $163.34] | -$223.32 | [-$846.07, $303.01] |
| 2025 (Jan-Aug) | fixed500 | halfway | base | 5 | gross_prefunding | 127 | -$181.87 | [-$503.08, $130.75] | -$256.92 | [-$877.91, $267.55] |
| 2025 (Jan-Aug) | fixed500 | halfway | stress | 0 | assignment_cash_net | 127 | $57.35 | [-$264.66, $369.44] | -$73.06 | [-$696.88, $452.98] |
| 2025 (Jan-Aug) | fixed500 | halfway | stress | 0 | gross_prefunding | 127 | -$9.85 | [-$336.39, $306.16] | -$140.26 | [-$761.19, $383.99] |
| 2025 (Jan-Aug) | fixed500 | halfway | stress | 1 | assignment_cash_net | 127 | -$2.00 | [-$323.13, $310.50] | -$100.10 | [-$724.67, $427.86] |
| 2025 (Jan-Aug) | fixed500 | halfway | stress | 1 | gross_prefunding | 127 | -$69.20 | [-$395.39, $246.87] | -$167.31 | [-$788.34, $355.92] |
| 2025 (Jan-Aug) | fixed500 | halfway | stress | 5 | assignment_cash_net | 127 | -$239.39 | [-$559.13, $72.39] | -$208.28 | [-$833.10, $322.71] |
| 2025 (Jan-Aug) | fixed500 | halfway | stress | 5 | gross_prefunding | 127 | -$306.59 | [-$632.05, $8.95] | -$275.48 | [-$898.75, $251.39] |
| 2025 (Jan-Aug) | fixed500 | midpoint | base | 0 | assignment_cash_net | 127 | $160.77 | [-$158.86, $471.48] | -$88.11 | [-$709.34, $436.04] |
| 2025 (Jan-Aug) | fixed500 | midpoint | base | 0 | gross_prefunding | 127 | $127.17 | [-$194.69, $440.11] | -$121.71 | [-$738.03, $401.96] |
| 2025 (Jan-Aug) | fixed500 | midpoint | base | 1 | assignment_cash_net | 127 | $101.42 | [-$218.19, $412.18] | -$115.15 | [-$736.15, $408.42] |
| 2025 (Jan-Aug) | fixed500 | midpoint | base | 1 | gross_prefunding | 127 | $67.82 | [-$253.83, $380.50] | -$148.75 | [-$768.07, $374.28] |
| 2025 (Jan-Aug) | fixed500 | midpoint | base | 5 | assignment_cash_net | 127 | -$135.96 | [-$454.45, $174.89] | -$223.32 | [-$846.07, $303.01] |
| 2025 (Jan-Aug) | fixed500 | midpoint | base | 5 | gross_prefunding | 127 | -$169.57 | [-$491.16, $142.83] | -$256.92 | [-$877.91, $267.55] |
| 2025 (Jan-Aug) | fixed500 | midpoint | stress | 0 | assignment_cash_net | 127 | $69.66 | [-$251.30, $381.60] | -$73.06 | [-$696.88, $452.98] |
| 2025 (Jan-Aug) | fixed500 | midpoint | stress | 0 | gross_prefunding | 127 | $2.45 | [-$323.57, $317.76] | -$140.26 | [-$761.19, $383.99] |
| 2025 (Jan-Aug) | fixed500 | midpoint | stress | 1 | assignment_cash_net | 127 | $10.31 | [-$310.75, $322.18] | -$100.10 | [-$724.67, $427.86] |
| 2025 (Jan-Aug) | fixed500 | midpoint | stress | 1 | gross_prefunding | 127 | -$56.89 | [-$383.07, $258.42] | -$167.31 | [-$788.34, $355.92] |
| 2025 (Jan-Aug) | fixed500 | midpoint | stress | 5 | assignment_cash_net | 127 | -$227.08 | [-$547.65, $83.87] | -$208.28 | [-$833.10, $322.71] |
| 2025 (Jan-Aug) | fixed500 | midpoint | stress | 5 | gross_prefunding | 127 | -$294.28 | [-$619.68, $21.52] | -$275.48 | [-$898.75, $251.39] |
| 2025 (Jan-Aug) | openrule | full_cross | base | 0 | assignment_cash_net | 127 | $760.59 | [$239.94, $1,374.74] | $536.32 | [-$16.87, $1,145.38] |
| 2025 (Jan-Aug) | openrule | full_cross | base | 0 | gross_prefunding | 127 | $711.28 | [$185.54, $1,329.45] | $487.01 | [-$65.30, $1,090.75] |
| 2025 (Jan-Aug) | openrule | full_cross | base | 1 | assignment_cash_net | 127 | $702.70 | [$179.90, $1,320.94] | $510.73 | [-$41.51, $1,120.32] |
| 2025 (Jan-Aug) | openrule | full_cross | base | 1 | gross_prefunding | 127 | $653.39 | [$125.64, $1,274.85] | $461.42 | [-$90.96, $1,063.93] |
| 2025 (Jan-Aug) | openrule | full_cross | base | 5 | assignment_cash_net | 127 | $471.13 | [-$56.23, $1,097.19] | $408.38 | [-$147.48, $1,014.04] |
| 2025 (Jan-Aug) | openrule | full_cross | base | 5 | gross_prefunding | 127 | $421.82 | [-$110.60, $1,051.34] | $359.07 | [-$194.00, $960.74] |
| 2025 (Jan-Aug) | openrule | full_cross | stress | 0 | assignment_cash_net | 127 | $695.48 | [$176.24, $1,309.71] | $577.37 | [$20.15, $1,189.78] |
| 2025 (Jan-Aug) | openrule | full_cross | stress | 0 | gross_prefunding | 127 | $596.86 | [$67.29, $1,216.52] | $478.76 | [-$73.34, $1,083.48] |
| 2025 (Jan-Aug) | openrule | full_cross | stress | 1 | assignment_cash_net | 127 | $637.58 | [$116.04, $1,255.98] | $551.78 | [-$6.04, $1,165.58] |
| 2025 (Jan-Aug) | openrule | full_cross | stress | 1 | gross_prefunding | 127 | $538.97 | [$7.68, $1,164.28] | $453.17 | [-$99.21, $1,056.57] |
| 2025 (Jan-Aug) | openrule | full_cross | stress | 5 | assignment_cash_net | 127 | $406.02 | [-$122.21, $1,032.37] | $449.43 | [-$108.85, $1,061.25] |
| 2025 (Jan-Aug) | openrule | full_cross | stress | 5 | gross_prefunding | 127 | $307.41 | [-$229.59, $940.86] | $350.82 | [-$203.62, $952.64] |
| 2025 (Jan-Aug) | openrule | halfway | base | 0 | assignment_cash_net | 127 | $772.89 | [$251.88, $1,387.95] | $536.32 | [-$16.87, $1,145.38] |
| 2025 (Jan-Aug) | openrule | halfway | base | 0 | gross_prefunding | 127 | $723.59 | [$197.51, $1,342.23] | $487.01 | [-$65.30, $1,090.75] |
| 2025 (Jan-Aug) | openrule | halfway | base | 1 | assignment_cash_net | 127 | $715.00 | [$191.79, $1,333.30] | $510.73 | [-$41.51, $1,120.32] |
| 2025 (Jan-Aug) | openrule | halfway | base | 1 | gross_prefunding | 127 | $665.69 | [$137.89, $1,287.09] | $461.42 | [-$90.96, $1,063.93] |
| 2025 (Jan-Aug) | openrule | halfway | base | 5 | assignment_cash_net | 127 | $483.43 | [-$44.29, $1,109.23] | $408.38 | [-$147.48, $1,014.04] |
| 2025 (Jan-Aug) | openrule | halfway | base | 5 | gross_prefunding | 127 | $434.13 | [-$98.53, $1,063.76] | $359.07 | [-$194.00, $960.74] |
| 2025 (Jan-Aug) | openrule | halfway | stress | 0 | assignment_cash_net | 127 | $707.78 | [$188.59, $1,322.30] | $577.37 | [$20.15, $1,189.78] |
| 2025 (Jan-Aug) | openrule | halfway | stress | 0 | gross_prefunding | 127 | $609.17 | [$80.15, $1,228.32] | $478.76 | [-$73.34, $1,083.48] |
| 2025 (Jan-Aug) | openrule | halfway | stress | 1 | assignment_cash_net | 127 | $649.89 | [$127.86, $1,268.05] | $551.78 | [-$6.04, $1,165.58] |
| 2025 (Jan-Aug) | openrule | halfway | stress | 1 | gross_prefunding | 127 | $551.28 | [$19.69, $1,176.15] | $453.17 | [-$99.21, $1,056.57] |
| 2025 (Jan-Aug) | openrule | halfway | stress | 5 | assignment_cash_net | 127 | $418.32 | [-$110.23, $1,044.33] | $449.43 | [-$108.85, $1,061.25] |
| 2025 (Jan-Aug) | openrule | halfway | stress | 5 | gross_prefunding | 127 | $319.71 | [-$216.91, $953.14] | $350.82 | [-$203.62, $952.64] |
| 2025 (Jan-Aug) | openrule | midpoint | base | 0 | assignment_cash_net | 127 | $785.20 | [$264.06, $1,400.43] | $536.32 | [-$16.87, $1,145.38] |
| 2025 (Jan-Aug) | openrule | midpoint | base | 0 | gross_prefunding | 127 | $735.89 | [$210.48, $1,355.41] | $487.01 | [-$65.30, $1,090.75] |
| 2025 (Jan-Aug) | openrule | midpoint | base | 1 | assignment_cash_net | 127 | $727.30 | [$204.26, $1,345.52] | $510.73 | [-$41.51, $1,120.32] |
| 2025 (Jan-Aug) | openrule | midpoint | base | 1 | gross_prefunding | 127 | $678.00 | [$150.91, $1,300.21] | $461.42 | [-$90.96, $1,063.93] |
| 2025 (Jan-Aug) | openrule | midpoint | base | 5 | assignment_cash_net | 127 | $495.74 | [-$32.51, $1,121.27] | $408.38 | [-$147.48, $1,014.04] |
| 2025 (Jan-Aug) | openrule | midpoint | base | 5 | gross_prefunding | 127 | $446.43 | [-$86.17, $1,076.09] | $359.07 | [-$194.00, $960.74] |
| 2025 (Jan-Aug) | openrule | midpoint | stress | 0 | assignment_cash_net | 127 | $720.09 | [$200.34, $1,335.11] | $577.37 | [$20.15, $1,189.78] |
| 2025 (Jan-Aug) | openrule | midpoint | stress | 0 | gross_prefunding | 127 | $621.48 | [$92.53, $1,240.65] | $478.76 | [-$73.34, $1,083.48] |
| 2025 (Jan-Aug) | openrule | midpoint | stress | 1 | assignment_cash_net | 127 | $662.19 | [$139.99, $1,279.72] | $551.78 | [-$6.04, $1,165.58] |
| 2025 (Jan-Aug) | openrule | midpoint | stress | 1 | gross_prefunding | 127 | $563.58 | [$31.61, $1,187.44] | $453.17 | [-$99.21, $1,056.57] |
| 2025 (Jan-Aug) | openrule | midpoint | stress | 5 | assignment_cash_net | 127 | $430.63 | [-$98.40, $1,056.37] | $449.43 | [-$108.85, $1,061.25] |
| 2025 (Jan-Aug) | openrule | midpoint | stress | 5 | gross_prefunding | 127 | $332.02 | [-$204.83, $966.11] | $350.82 | [-$203.62, $952.64] |

### q0 absolute intervals retained

| Year | Fill | Cost | Slippage bp | Funding | n | Mean | Absolute 95% CI |
|---|---|---|---|---|---|---|---|
| 2022 | full_cross | base | 0 | assignment_cash_net | 63 | $114.07 | [-$149.14, $366.79] |
| 2022 | full_cross | base | 0 | gross_prefunding | 63 | $114.07 | [-$149.14, $366.79] |
| 2022 | full_cross | base | 1 | assignment_cash_net | 63 | $96.47 | [-$166.32, $347.98] |
| 2022 | full_cross | base | 1 | gross_prefunding | 63 | $96.47 | [-$166.32, $347.98] |
| 2022 | full_cross | base | 5 | assignment_cash_net | 63 | $26.09 | [-$237.58, $277.62] |
| 2022 | full_cross | base | 5 | gross_prefunding | 63 | $26.09 | [-$237.58, $277.62] |
| 2022 | full_cross | stress | 0 | assignment_cash_net | 63 | $42.28 | [-$223.81, $293.62] |
| 2022 | full_cross | stress | 0 | gross_prefunding | 63 | $42.28 | [-$223.81, $293.62] |
| 2022 | full_cross | stress | 1 | assignment_cash_net | 63 | $24.68 | [-$241.07, $276.19] |
| 2022 | full_cross | stress | 1 | gross_prefunding | 63 | $24.68 | [-$241.07, $276.19] |
| 2022 | full_cross | stress | 5 | assignment_cash_net | 63 | -$45.69 | [-$314.91, $205.62] |
| 2022 | full_cross | stress | 5 | gross_prefunding | 63 | -$45.69 | [-$314.91, $205.62] |
| 2022 | halfway | base | 0 | assignment_cash_net | 63 | $125.78 | [-$138.10, $378.44] |
| 2022 | halfway | base | 0 | gross_prefunding | 63 | $125.78 | [-$138.10, $378.44] |
| 2022 | halfway | base | 1 | assignment_cash_net | 63 | $108.18 | [-$154.80, $359.43] |
| 2022 | halfway | base | 1 | gross_prefunding | 63 | $108.18 | [-$154.80, $359.43] |
| 2022 | halfway | base | 5 | assignment_cash_net | 63 | $37.80 | [-$225.61, $289.69] |
| 2022 | halfway | base | 5 | gross_prefunding | 63 | $37.80 | [-$225.61, $289.69] |
| 2022 | halfway | stress | 0 | assignment_cash_net | 63 | $53.99 | [-$211.28, $305.69] |
| 2022 | halfway | stress | 0 | gross_prefunding | 63 | $53.99 | [-$211.28, $305.69] |
| 2022 | halfway | stress | 1 | assignment_cash_net | 63 | $36.40 | [-$229.42, $288.38] |
| 2022 | halfway | stress | 1 | gross_prefunding | 63 | $36.40 | [-$229.42, $288.38] |
| 2022 | halfway | stress | 5 | assignment_cash_net | 63 | -$33.98 | [-$302.88, $217.39] |
| 2022 | halfway | stress | 5 | gross_prefunding | 63 | -$33.98 | [-$302.88, $217.39] |
| 2022 | midpoint | base | 0 | assignment_cash_net | 63 | $137.48 | [-$126.58, $390.14] |
| 2022 | midpoint | base | 0 | gross_prefunding | 63 | $137.48 | [-$126.58, $390.14] |
| 2022 | midpoint | base | 1 | assignment_cash_net | 63 | $119.89 | [-$143.43, $370.76] |
| 2022 | midpoint | base | 1 | gross_prefunding | 63 | $119.89 | [-$143.43, $370.76] |
| 2022 | midpoint | base | 5 | assignment_cash_net | 63 | $49.51 | [-$213.72, $301.70] |
| 2022 | midpoint | base | 5 | gross_prefunding | 63 | $49.51 | [-$213.72, $301.70] |
| 2022 | midpoint | stress | 0 | assignment_cash_net | 63 | $65.70 | [-$200.07, $317.50] |
| 2022 | midpoint | stress | 0 | gross_prefunding | 63 | $65.70 | [-$200.07, $317.50] |
| 2022 | midpoint | stress | 1 | assignment_cash_net | 63 | $48.11 | [-$217.71, $300.15] |
| 2022 | midpoint | stress | 1 | gross_prefunding | 63 | $48.11 | [-$217.71, $300.15] |
| 2022 | midpoint | stress | 5 | assignment_cash_net | 63 | -$22.27 | [-$291.44, $229.14] |
| 2022 | midpoint | stress | 5 | gross_prefunding | 63 | -$22.27 | [-$291.44, $229.14] |
| 2024 | full_cross | base | 0 | assignment_cash_net | 195 | -$476.37 | [-$761.29, -$206.88] |
| 2024 | full_cross | base | 0 | gross_prefunding | 195 | -$476.37 | [-$761.29, -$206.88] |
| 2024 | full_cross | base | 1 | assignment_cash_net | 195 | -$508.10 | [-$795.19, -$237.03] |
| 2024 | full_cross | base | 1 | gross_prefunding | 195 | -$508.10 | [-$795.19, -$237.03] |
| 2024 | full_cross | base | 5 | assignment_cash_net | 195 | -$635.02 | [-$929.39, -$357.26] |
| 2024 | full_cross | base | 5 | gross_prefunding | 195 | -$635.02 | [-$929.39, -$357.26] |
| 2024 | full_cross | stress | 0 | assignment_cash_net | 195 | -$588.40 | [-$878.70, -$313.25] |
| 2024 | full_cross | stress | 0 | gross_prefunding | 195 | -$588.40 | [-$878.70, -$313.25] |
| 2024 | full_cross | stress | 1 | assignment_cash_net | 195 | -$620.13 | [-$912.50, -$343.69] |
| 2024 | full_cross | stress | 1 | gross_prefunding | 195 | -$620.13 | [-$912.50, -$343.69] |
| 2024 | full_cross | stress | 5 | assignment_cash_net | 195 | -$747.05 | [-$1,049.06, -$462.49] |
| 2024 | full_cross | stress | 5 | gross_prefunding | 195 | -$747.05 | [-$1,049.06, -$462.49] |
| 2024 | halfway | base | 0 | assignment_cash_net | 195 | -$466.06 | [-$751.09, -$196.84] |
| 2024 | halfway | base | 0 | gross_prefunding | 195 | -$466.06 | [-$751.09, -$196.84] |
| 2024 | halfway | base | 1 | assignment_cash_net | 195 | -$497.79 | [-$784.76, -$226.58] |
| 2024 | halfway | base | 1 | gross_prefunding | 195 | -$497.79 | [-$784.76, -$226.58] |
| 2024 | halfway | base | 5 | assignment_cash_net | 195 | -$624.71 | [-$918.96, -$346.54] |
| 2024 | halfway | base | 5 | gross_prefunding | 195 | -$624.71 | [-$918.96, -$346.54] |
| 2024 | halfway | stress | 0 | assignment_cash_net | 195 | -$578.09 | [-$868.76, -$302.67] |
| 2024 | halfway | stress | 0 | gross_prefunding | 195 | -$578.09 | [-$868.76, -$302.67] |
| 2024 | halfway | stress | 1 | assignment_cash_net | 195 | -$609.82 | [-$901.80, -$332.88] |
| 2024 | halfway | stress | 1 | gross_prefunding | 195 | -$609.82 | [-$901.80, -$332.88] |
| 2024 | halfway | stress | 5 | assignment_cash_net | 195 | -$736.74 | [-$1,039.02, -$452.69] |
| 2024 | halfway | stress | 5 | gross_prefunding | 195 | -$736.74 | [-$1,039.02, -$452.69] |
| 2024 | midpoint | base | 0 | assignment_cash_net | 195 | -$455.75 | [-$740.94, -$186.31] |
| 2024 | midpoint | base | 0 | gross_prefunding | 195 | -$455.75 | [-$740.94, -$186.31] |
| 2024 | midpoint | base | 1 | assignment_cash_net | 195 | -$487.48 | [-$774.27, -$216.11] |
| 2024 | midpoint | base | 1 | gross_prefunding | 195 | -$487.48 | [-$774.27, -$216.11] |
| 2024 | midpoint | base | 5 | assignment_cash_net | 195 | -$614.40 | [-$908.56, -$335.83] |
| 2024 | midpoint | base | 5 | gross_prefunding | 195 | -$614.40 | [-$908.56, -$335.83] |
| 2024 | midpoint | stress | 0 | assignment_cash_net | 195 | -$567.78 | [-$858.80, -$292.62] |
| 2024 | midpoint | stress | 0 | gross_prefunding | 195 | -$567.78 | [-$858.80, -$292.62] |
| 2024 | midpoint | stress | 1 | assignment_cash_net | 195 | -$599.51 | [-$891.64, -$322.45] |
| 2024 | midpoint | stress | 1 | gross_prefunding | 195 | -$599.51 | [-$891.64, -$322.45] |
| 2024 | midpoint | stress | 5 | assignment_cash_net | 195 | -$726.43 | [-$1,028.25, -$442.13] |
| 2024 | midpoint | stress | 5 | gross_prefunding | 195 | -$726.43 | [-$1,028.25, -$442.13] |
| 2025 (Jan-Aug) | full_cross | base | 0 | assignment_cash_net | 127 | $224.27 | [-$370.84, $884.24] |
| 2025 (Jan-Aug) | full_cross | base | 0 | gross_prefunding | 127 | $224.27 | [-$370.84, $884.24] |
| 2025 (Jan-Aug) | full_cross | base | 1 | assignment_cash_net | 127 | $191.97 | [-$406.29, $854.57] |
| 2025 (Jan-Aug) | full_cross | base | 1 | gross_prefunding | 127 | $191.97 | [-$406.29, $854.57] |
| 2025 (Jan-Aug) | full_cross | base | 5 | assignment_cash_net | 127 | $62.75 | [-$541.99, $733.69] |
| 2025 (Jan-Aug) | full_cross | base | 5 | gross_prefunding | 127 | $62.75 | [-$541.99, $733.69] |
| 2025 (Jan-Aug) | full_cross | stress | 0 | assignment_cash_net | 127 | $118.11 | [-$483.33, $789.27] |
| 2025 (Jan-Aug) | full_cross | stress | 0 | gross_prefunding | 127 | $118.11 | [-$483.33, $789.27] |
| 2025 (Jan-Aug) | full_cross | stress | 1 | assignment_cash_net | 127 | $85.80 | [-$518.22, $759.24] |
| 2025 (Jan-Aug) | full_cross | stress | 1 | gross_prefunding | 127 | $85.80 | [-$518.22, $759.24] |
| 2025 (Jan-Aug) | full_cross | stress | 5 | assignment_cash_net | 127 | -$43.42 | [-$656.48, $632.41] |
| 2025 (Jan-Aug) | full_cross | stress | 5 | gross_prefunding | 127 | -$43.42 | [-$656.48, $632.41] |
| 2025 (Jan-Aug) | halfway | base | 0 | assignment_cash_net | 127 | $236.57 | [-$357.82, $896.99] |
| 2025 (Jan-Aug) | halfway | base | 0 | gross_prefunding | 127 | $236.57 | [-$357.82, $896.99] |
| 2025 (Jan-Aug) | halfway | base | 1 | assignment_cash_net | 127 | $204.27 | [-$393.57, $866.71] |
| 2025 (Jan-Aug) | halfway | base | 1 | gross_prefunding | 127 | $204.27 | [-$393.57, $866.71] |
| 2025 (Jan-Aug) | halfway | base | 5 | assignment_cash_net | 127 | $75.05 | [-$530.21, $745.96] |
| 2025 (Jan-Aug) | halfway | base | 5 | gross_prefunding | 127 | $75.05 | [-$530.21, $745.96] |
| 2025 (Jan-Aug) | halfway | stress | 0 | assignment_cash_net | 127 | $130.41 | [-$471.40, $801.31] |
| 2025 (Jan-Aug) | halfway | stress | 0 | gross_prefunding | 127 | $130.41 | [-$471.40, $801.31] |
| 2025 (Jan-Aug) | halfway | stress | 1 | assignment_cash_net | 127 | $98.11 | [-$505.98, $771.54] |
| 2025 (Jan-Aug) | halfway | stress | 1 | gross_prefunding | 127 | $98.11 | [-$505.98, $771.54] |
| 2025 (Jan-Aug) | halfway | stress | 5 | assignment_cash_net | 127 | -$31.11 | [-$644.23, $644.31] |
| 2025 (Jan-Aug) | halfway | stress | 5 | gross_prefunding | 127 | -$31.11 | [-$644.23, $644.31] |
| 2025 (Jan-Aug) | midpoint | base | 0 | assignment_cash_net | 127 | $248.88 | [-$345.90, $909.60] |
| 2025 (Jan-Aug) | midpoint | base | 0 | gross_prefunding | 127 | $248.88 | [-$345.90, $909.60] |
| 2025 (Jan-Aug) | midpoint | base | 1 | assignment_cash_net | 127 | $216.57 | [-$380.83, $878.66] |
| 2025 (Jan-Aug) | midpoint | base | 1 | gross_prefunding | 127 | $216.57 | [-$380.83, $878.66] |
| 2025 (Jan-Aug) | midpoint | base | 5 | assignment_cash_net | 127 | $87.36 | [-$518.42, $758.33] |
| 2025 (Jan-Aug) | midpoint | base | 5 | gross_prefunding | 127 | $87.36 | [-$518.42, $758.33] |
| 2025 (Jan-Aug) | midpoint | stress | 0 | assignment_cash_net | 127 | $142.72 | [-$459.30, $813.08] |
| 2025 (Jan-Aug) | midpoint | stress | 0 | gross_prefunding | 127 | $142.72 | [-$459.30, $813.08] |
| 2025 (Jan-Aug) | midpoint | stress | 1 | assignment_cash_net | 127 | $110.41 | [-$494.40, $782.95] |
| 2025 (Jan-Aug) | midpoint | stress | 1 | gross_prefunding | 127 | $110.41 | [-$494.40, $782.95] |
| 2025 (Jan-Aug) | midpoint | stress | 5 | assignment_cash_net | 127 | -$18.80 | [-$631.31, $657.31] |
| 2025 (Jan-Aug) | midpoint | stress | 5 | gross_prefunding | 127 | -$18.80 | [-$631.31, $657.31] |

## Earlier study context and limits

The reviewed stock-reference study found no dependable executable edge. It compared stock-reference inputs while holding the option sample fixed. The overnight hedge study answers a separate after-cost question.

The earlier matched-moneyness gap and expiry carry address a different question. The stock-reference comparison did not create an edge.

These are descriptive historical comparisons on periods already examined, not a predictive holdout. Option quotes from 15:59 ET are used for 2024 and 2025 only and are paired with later close references. Clock semantics for 2019 and 2022 remain unresolved. The assignment threshold is a proxy; partial exercise is unobserved. Daily OHLC prices do not prove order availability, fills, capacity, or margin. No Sharpe, ROI, or operational profit claim is made.

The 36 no-hedge, zero-slippage summary controls reproduce the earlier study. The primary table uses 1 bp stock slippage; its 2022 no-hedge mean of $96.47 versus the earlier $114.07 reflects that added assumption, not a source-data change.

## Method and reproducibility

The primary case is full-cross, base costs, gross prefunding, and 1 bp slippage. The option and stock reference use a one-calendar-day expiration design with modeled buys at the daily close. Residual stock is closed at the next session open, leaving the modeled hedge flat.

DTE 1 quotes do not provide same-day delta or closeout.

| Evidence field | Value |
|---|---|
| Status | EVALUATED |
| Evaluated SHA | db5d980c7abc344af02e8ae98fc426da92df433e |
| Clean worktree | True |
| Run manifest SHA-256 | 237c589993798479c26243a1d66acec3a04fc7c8c1b4cebf4a97e4958e583d0e |
| Protocol SHA-256 | 30eae811523310cb174fb0c8b244337031b00f0b16f479d954a495d531040731 |
| Normalized selection SHA-256 | 8156d9030ca082af279f2fd3c99cfb445fa21237a09b1782abb0911b7d4ac8f7 |
| Input manifest SHA-256 | 576d58194e467bfb2b3ab7ae7ea49cede871a21f276330a6fd1ab447f82484e5 |
| Uncertainty source SHA-256 | b9b43b4978d8fa8ddd3ca5527caa64318f8be1f7e131ae056d5221e361271442 |
| Independent validation result SHA-256 | 640193de6b4c237dd39a02e264d57d7d4256ff0454571381b037a30361b3f66c |
| Independent validation index SHA-256 | 42ba3e479450a58ff2becee67d66a6e865be4a4ff639388a63fe8847a9409f57 |
| Validation status / comparisons / mismatches | PASS / 2,361,472 / 0 |
| Full repository tests | 444 passed (206 warnings) |
| Focused overnight hedge tests | 26 passed |
| Run started UTC | 2026-10-29T17:18:26.473822+00:00 |
| Run ended UTC | 2026-10-29T17:18:32.167674+00:00 |
| Renderer SHA-256 | 551a08e324febb047d31144102a31e8381e6dd1069ee9960506fb75eea5702bc |
| Frozen aggregate SHA-256 | 41b02de0eef0362f29dfed4c537e38e18fd9bd58982e955f1a7852a452da5325 |
| Output PDF SHA-256 | 39ebfeee8b284150d0d4448beda0e573b808ecfb7fadc6358cb93b02798f3e45 |

### Bound source hashes

Inventory paths are relative to the reviewed input copy. The 40 copied files and the copy inventory are all bound by SHA-256.

| Source file | Bytes | SHA-256 |
|---|---|---|
| candidate.md | 9824 | 30eae811523310cb174fb0c8b244337031b00f0b16f479d954a495d531040731 |
| copy-inventory.json | 6223 | 3d805b1b4fc9452fe1fd73039da7cab55868ddd5af2aec77501b493071ebaad8 |
| evaluation-execution-02.json | 710 | 3837f1ec56c962e1bdbf3830b0f873911288d23a38f76333a959b86961a27d2f |
| evaluation-execution-02.stderr | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| evaluation-execution-02.stdout | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| evaluation/case-ledgers.json | 84302531 | 17a11c5cb21fcf00109a5f9b80f16aca8dc5be104f0d8c16e37daae2f8bcf638 |
| evaluation/coverage.json | 136 | d95911453ae38ff5fab8b18dec68cc645894968d5c5cce12ca9f55aa4c6a1f53 |
| evaluation/draw-metadata.json | 442504 | bff07fc0d4419a6d4c26b97d2f9e7d5314748917d3de5c39bbd9225b4d19a8b6 |
| evaluation/manifest.json | 23202 | 237c589993798479c26243a1d66acec3a04fc7c8c1b4cebf4a97e4958e583d0e |
| evaluation/normalized-selection-receipt.json | 435 | 5d56bfb7c0f69022cb0b2e8e319c9f3f72b9679b29982db6f01b3cd4c4d54e19 |
| evaluation/parity.json | 9718 | 18d6e8358b52586f0cf1207ca02eccf8dbcfa4110a9909c76e8a6d4bb9c71816 |
| evaluation/source-audit.json | 11821 | 5230e814b168bb546ab5de99093899c3252f538204336ca3f46a9bee370a11ff |
| evaluation/stderr.log | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| evaluation/stdout.log | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| evaluation/summaries.json | 663078 | 29a68896ee23d5cf02237ca089bc7725765877d135130a4040486bf0f9dbf02b |
| evaluation/summary.json | 195 | c71e9b7a434fea671c2c63716fb7d2d38e6e7a608a1b69c494da5e146bdea82a |
| evaluation/uncertainty.json | 1271190 | b9b43b4978d8fa8ddd3ca5527caa64318f8be1f7e131ae056d5221e361271442 |
| input-manifest.json | 11794 | 576d58194e467bfb2b3ab7ae7ea49cede871a21f276330a6fd1ab447f82484e5 |
| prepared/normalized-selection-receipt.json | 435 | 5d56bfb7c0f69022cb0b2e8e319c9f3f72b9679b29982db6f01b3cd4c4d54e19 |
| prepared/normalized-selection.json | 1588083 | 8156d9030ca082af279f2fd3c99cfb445fa21237a09b1782abb0911b7d4ac8f7 |
| prepared/source-audit.json | 22561 | 6421471fa661a3cb749083ce5c7a66d0c65e96521347a747984c9faae5cb523a |
| prior-reviewed-aggregate.json | 730048 | 2cb60f7a82682b7a13cac40cacfe1c736063373ec0a3458b5e04365f821018c6 |
| test-adapter-final-focused.log | 401 | 1ff1126a0d889b346e2f7438f38988aee841384f947e7b212732a96ea8b218dc |
| test-adapter-final-full.log | 4922 | b589763a50bbcf6601ef6c24a2fd7107ed4c3c9514c433ec3d5e075a3acad073 |
| validation/actual-validation-01.execution.json | 2227 | 33fe3d2f967b9d153d2d89be893272001ccc6860d3f6357df657f9366d992478 |
| validation/actual-validation-01.json | 5525 | 640193de6b4c237dd39a02e264d57d7d4256ff0454571381b037a30361b3f66c |
| validation/actual-validation-01.stderr | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| validation/actual-validation-01.stdout | 5171 | f9749203f1e1f2e988f2fa36e720814fdd23d98c108c8c2e9304e41df2ce30bf |
| validation/independent_core.py | 10243 | 76f71f274e7a688e32c769e8d1c063e75c67efaabbede41ce74131d9bdc26307 |
| validation/post-validation-source-receipt.json | 239 | 1dc820c507e7f629f26f281e66fadef4641a56a6f21f8a9480e29e1d2a589e42 |
| validation/schema-selftest.json | 324 | e46ffc3add654cc6948fcb1b717d7d32523fb8f8643876915419e1872d09e0a9 |
| validation/synthetic-selftest.execution.json | 684 | d3395c8bfc3ade7e43234e7f6410d742a3fd6ffb71fa9151a5e25762c4f7ba1b |
| validation/synthetic-selftest.stderr | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |
| validation/synthetic-selftest.stdout | 84 | 60e3da4d1e877e8394d5654ef449582757849771a35b0c674c0154489d7ea8a2 |
| validation/validation-index-01.json | 2447 | 34975a53f10ad0fc8f342fcde19d319a99f9c29abcc31b594f09e989960d2935 |
| validation/validation-index-02.json | 8286 | 42ba3e479450a58ff2becee67d66a6e865be4a4ff639388a63fe8847a9409f57 |
| validation/validation-plan.md | 1465 | 833f453878bf4592d975f1752cefab6c134f70aa6aa012fa941a000e825e21e3 |
| validation/verify_outputs-v1.py | 11339 | 21e68713f8e1086b266f8c1d6df1d2dba30cbe0b323d539974d0f2628b8d196f |
| validation/verify_outputs-v2.py | 17055 | 3d1475f421060451891644fcc65e30014557fc2b0cfdf361f67983fcae929395 |
| validation/verify_outputs-v3.py | 18385 | 4c28df94d94c62cc74fced28af14600befd25b666bc53434bcc89dd3250f69f1 |
| validation/verify_outputs.py | 19819 | 260403a218a6ec11b3bf59cb89876e8a766bd024e68c699f57fab868d02b22b2 |

Sources: [OIC assignment and exercise](https://www.optionseducation.org/referencelibrary/faq/options-assignment), [NYSE opening and closing auctions](https://www.nyse.com/markets/nyse/trading-info).
