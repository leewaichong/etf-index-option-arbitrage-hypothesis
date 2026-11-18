# SPY/SPX morning execution study

## Verdict

Across the three Jan-Aug periods, the entry-close/open mean was positive in 2 of 3; the paired timing delta was positive in 3 of 3, and its 95% interval excluded zero in 1 of 3. Timing direction changed between Jan-Aug and full-year results in 1 of the two 2023/2024 comparisons. For Jan-Aug 2025, the combined open-buy versus legacy mean delta was −$249 per package, with 95% interval [−$898, $392]. These exposed historical periods are descriptive, not holdouts.

The primary open purchase moves the hedge buy earlier, changing intraday stock exposure. It does not isolate an option edge or remove residual overnight stock risk. Do not read the result as arbitrage or a proven trading edge.

Primary case: full-cross option fills, base costs, 1 bp stock slippage, gross prefunding, and 6.5-hour open-funding convention.

## Primary net mean by package

USD per package. Brackets show the paired-cluster 95% interval for the open-buy arm.

| Period | n | Entry-close / open | Same signal / close | Legacy open signal / close | Fixed 500 / open |
|---|---:|---:|---:|---:|---:|
| Jan-Aug 2023 | 131 | $508 [$116, $914] | $185 | −$56 | $117 |
| Jan-Aug 2024 | 131 | −$22 [−$623, $523] | −$259 | −$146 | −$194 |
| Jan-Aug 2025 | 127 | $405 [−$399, $1,229] | $117 | $653 | $163 |
| Full 2023 | 196 | $268 [−$71, $607] | $58 | −$49 | −$16 |
| Full 2024 | 195 | −$268 [−$768, $199] | −$236 | −$90 | −$238 |

The three Jan-Aug cohorts are exposed historical periods, not holdouts. Full-year 2023 and 2024 are secondary comparisons.

## Timing and signal deltas

Paired mean net USD per package. Positive values favor the left-hand arm named in the comparison. Each interval uses 5,000 expiry-week cluster bootstrap draws, seed 20261118.

| Period | Open vs same-signal close | Entry-close vs legacy signal | Combined vs legacy | Fixed-500 open vs close |
|---|---:|---:|---:|---:|
| Jan-Aug 2023 | $322 [$19, $635] | $242 [−$22, $520] | $564 [$125, $1,029] | $175 |
| Jan-Aug 2024 | $237 [−$88, $593] | −$113 [−$553, $260] | $125 [−$469, $693] | $48 |
| Jan-Aug 2025 | $288 [−$357, $995] | −$537 [−$971, −$134] | −$249 [−$898, $392] | $120 |
| Full 2023 | $211 [−$57, $473] | $107 [−$117, $334] | $317 [−$59, $705] | $74 |
| Full 2024 | −$32 [−$375, $307] | −$146 [−$514, $155] | −$178 [−$662, $292] | −$26 |

## Full-cross cost sensitivity

USD per package.

| Period | Scenario | Gross mean | Mean costs | Net mean |
|---|---|---:|---:|---:|
| Jan-Aug 2023 | Base, 1 bp, 6.5 hours | $622 | $115 | $508 |
| Jan-Aug 2023 | Stress, 1 bp, 6.5 hours | $622 | $210 | $412 |
| Jan-Aug 2023 | Base, 5 bp, 6.5 hours | $622 | $271 | $351 |
| Jan-Aug 2023 | Base, 1 bp, full-day funding | $622 | $135 | $487 |
| Jan-Aug 2024 | Base, 1 bp, 6.5 hours | $120 | $142 | −$22 |
| Jan-Aug 2024 | Stress, 1 bp, 6.5 hours | $120 | $260 | −$139 |
| Jan-Aug 2024 | Base, 5 bp, 6.5 hours | $120 | $323 | −$203 |
| Jan-Aug 2024 | Base, 1 bp, full-day funding | $120 | $167 | −$46 |
| Jan-Aug 2025 | Base, 1 bp, 6.5 hours | $569 | $164 | $405 |
| Jan-Aug 2025 | Stress, 1 bp, 6.5 hours | $569 | $301 | $269 |
| Jan-Aug 2025 | Base, 5 bp, 6.5 hours | $569 | $394 | $175 |
| Jan-Aug 2025 | Base, 1 bp, full-day funding | $569 | $193 | $376 |

The CSV retains all seven arms, all 36 declared fill, cost, slippage, and funding combinations, and all five cohorts. No grid cell was selected as a preferred result.

## Method and limits

Package: 10 short SPY calls and one long SPXW call, multiplier 100. The primary q rule buys 1,000 SPY shares when entry-date close is at least selected strike + $0.01; otherwise q=0. It buys at expiry open. The same-signal close arm changes only fill timing. Fixed-500 arms are diagnostics. The legacy arm uses expiry-open signal and expiry-close purchase. Same-open idealized uses same-open signal and fill, so it is a look-ahead diagnostic and not executable.

The option package enters at a theoretical daily close one calendar day before expiry. Residual stock exits at next-session open. Residual stock can remain between 1,000 shares short and 1,000 shares long. The fixed-500 arms leave 500 shares long or short. Funding uses gross-prefund convention with 6.5/24 extra day for open buys, one day in sensitivity, and zero for close buys. This is a conservative convention, not a broker holding clock. Costs include fees, borrow, premium and hedge funding, and slippage. Distributions follow the signed residual convention.

SPY options are American and physically settled; SPXW options are European and cash settled. Early or partial assignment is not modeled. Option quote timing at 15:59 is verified for 2024 and 2025 only; 2023 is unverified. Option entries use theoretical close references, while the stock-close reference may be later. Daily SPY open is a proxy, not a proven broker auction or MOO fill. Margin and capacity are not established. Repeated observations are not independent. The bootstrap intervals describe these historical samples and do not predict future results.

Next step, planned and not run: a forward paper study with timestamped option quotes and auction fills, assignment handling, measured margin and capacity, and a predeclared holdout. No paper execution or trading action is authorized by this report.

## Provenance

Study Git SHA: `561e7839485f0d454181c9174c86dc1584333e27`. Protocol SHA-256: `cee81a7cad5b4c43c17b4d413a623daf1db14ce72f27b3f646ddb17269d157cf`. Evaluator input-manifest SHA-256: `25e0a86b8c8b3996342343a50213fd6199827308fa869c9b982e637eb17703ae`. Source-inventory SHA-256: `aacd44bf78c5fb26b63a1192eb0633531e72a3af6ab977417759db1a460dc387`.
Evaluator SHA-256: `2122dbf48cfddfed0aaf313eb2ee3c0416a8f0774044d3d175b602e003d251d3`. Checker SHA-256: `33b2c2a441a74a6fe123a8435e42848d9d92685fe5426961375b40ab7217aa49`. Checker core SHA-256: `fcc024eccdcc513107c6248ba48e4f0061ed1ca7bdc73e0115c7dc0fb5421e8a`.
Validation status: independently validated. This renderer does not include source paths or licensed raw rows.
