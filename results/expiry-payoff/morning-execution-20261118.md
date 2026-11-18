# Morning execution study, 18 November 2026

## Finding

The test asked whether buying the stock hedge at expiry-session open, using a signal fixed at the prior close, improved the earlier expiry-payoff results. The open-buy mean was positive in two of the three shared January-to-August samples and negative in 2024. Across the full 2023 and 2024 samples it was positive in 2023 and negative in 2024. Those results do not establish a dependable, repeatable after-cost edge. A positive sample mean is not risk-free arbitrage, and the hedge leaves overnight stock exposure.

This is a separate question from the original matched-moneyness hypothesis. That study asked whether economically comparable short-expiry SPY and SPXW calls retain a persistent price-level gap after matching moneyness. Its close-based evidence rejected a dependable meaningful level gap. The current report tests a stock hedge around expiry payoff; it does not change or retest that conclusion.

The broader expiry/carry thesis is that physical settlement, cash settlement, and stock cover can create apparent P&L differences. Any gain would need to survive spreads, fees, borrow, funding, distributions, and residual stock risk, then recur in separate periods. The current historical samples are exposed data, not untouched holdouts.

## Primary outcomes

Mean net USD per package. Primary case uses full-cross option fills, base costs, 1 bp stock slippage, gross prefunding, and the 6.5-hour open-purchase funding convention. Values are rounded to whole dollars as in the approved report.

| Period | n | Prior-close signal, open buy | Same signal, close buy | Legacy open signal, close buy |
|---|---:|---:|---:|---:|
| Jan-Aug 2023 | 131 | $508 | $185 | -$56 |
| Jan-Aug 2024 | 131 | -$22 | -$259 | -$146 |
| Jan-Aug 2025 | 127 | $405 | $117 | $653 |
| Full 2023 | 196 | $268 | $58 | -$49 |
| Full 2024 | 195 | -$268 | -$236 | -$90 |

The timing comparison holds the prior-close signal and share quantity constant, changing only the purchase from close to expiry open. Its mean delta was +$322, +$237, and +$288 across the three shared periods, but only one of those three 95% expiry-week intervals excluded zero. Across full 2024 the timing delta was -$32. For January-August 2025, the -$537 signal-change delta outweighed the +$288 timing delta, leaving a combined -$249 change versus legacy. All periods are historical and descriptive; the combined comparison is not a pure timing effect. The open-buy arm's 95% intervals were [$116, $914] for 2023, [-$623, $523] for 2024, and [-$399, $1,229] for 2025. The breadth of those ranges matters more than the positive means in two samples.

## Method

Each package contains 10 short SPY calls and one long SPXW call, multiplier 100. The theoretical option entry uses daily close one calendar day before expiry. The primary rule sets q to 1,000 shares when entry-date close is at least the selected strike plus $0.01, otherwise q is zero. It buys q at expiry-session open; residual stock exits at the next session's open. The same-signal close arm holds q fixed and changes only purchase timing. The legacy arm uses an expiry-open signal and expiry-close purchase, so it changes both signal and fill.

SPY options are American style with delivery of shares; SPX options are European style with cash settlement, as described by [Cboe's product comparison](https://www.cboe.com/tradable-products/product-comparison). See also [Cboe's SPX Weeklys specifications](https://www.cboe.com/tradable_products/sp_500/spx_weekly_options/specifications/). Modeled costs include option and stock fees, borrow, funding, and slippage. Distribution amounts are signed cash flows based on residual shares, not fees. The study does not show that all cost assumptions produce negative means; for example, the selected open-buy means were positive in two shared periods under base costs.

## Limits and status

The 15:59 option quotes are compared with a later stock-close reference. The quote clock is verified for 2024 and 2025; the 2023 clock is unverified. Daily open is a proxy, not evidence of an auction or market-on-open fill. Early or partial assignment is not modeled. Residual stock may range from 1,000 shares short to 1,000 long. The work does not establish synchronized execution, margin, capacity, or actual broker fills. The samples were historically exposed, and bootstrap intervals describe those samples rather than future outcomes.

**Implemented:** the frozen study and report renderer. **Locally verified:** on evaluation SHA `561e7839485f0d454181c9174c86dc1584333e27`, the initial scientific suite passed 507 tests with three optional PDF modules skipped. On final SHA `b97e73158c5c96cfb65b5d0611cefe1caab918af`, the final scientific suite passed 507 tests with four optional PDF modules skipped. Separately, the renderer's three focused PDF tests and the validator's 15 unit tests passed. **Evaluated:** the deterministic financial evaluation ran on the clean evaluation SHA and passed independent validation: 1,996,506 numeric checks, maximum absolute error `1.0550138540565968e-10` against tolerance `1e-7`. This publication adds only report aggregates; it does not claim a new evaluation of public code. A historical rerun from the public checkout was NOT RUN because licensed inputs and private controls are absent.

The next study of timestamped quotes, auction fills, assignment, margin, capacity, and a predeclared prospective test is PLANNED, NOT RUN.

## Files and provenance

- [Approved PDF report](../../reports/expiry-payoff/morning-execution-study-20261118.pdf), SHA-256 `bedeb126e4bbab1218ca838ad71aed41b72cbc1c130b5b5c564c4c135847710d`.
- [Approved Markdown report](../../reports/expiry-payoff/morning-execution-study-20261118.md).
- [Aggregate CSV](../../reports/expiry-payoff/morning-execution-study-20261118.csv), containing 1,260 cohort/scenario summary rows.

The report records protocol SHA-256 `cee81a7cad5b4c43c17b4d413a623daf1db14ce72f27b3f646ddb17269d157cf` and input-manifest SHA-256 `25e0a86b8c8b3996342343a50213fd6199827308fa869c9b982e637eb17703ae`. Independent validation and report QA are documented in the approved report archive. The CSV contains aggregate summaries, not raw market rows.
