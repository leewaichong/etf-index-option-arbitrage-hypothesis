# OptionMetrics replication

**Status: EVALUATED before this public source export.** The clean evaluated
commit was `72c382db4665e1277426c905baf0a56236f135c8`. This result is not a
result of the public source changes.

The full-cross expiry means were +$41.09 per hypothetical package in 2024
(`n=195`) and +$18.45 in January to August 2025 (`n=127`). Base-cost means were
-$476.37 and +$224.27. All values are USD per 10-short-SPY / 1-long-SPXW
package, with 100 multipliers and equal weight per expiry. The samples had known
data during research and are not predictive holdouts. No dependable executable
edge was established.

The protocol selected one expiry pair at one-calendar-day DTE, using nearest-ATM
SPY within 2% and SPXW normalized moneyness within 0.001. The primary entry was
the full cross: SPY bid and SPXW ask. The modeled cost ledger includes option
fees, conditional stock cover, borrow and entry-debit funding. It is not a record
of actual fills or charges.

| Evaluation | UTC | Selection snapshot SHA-256 | Independent checks |
|---|---|---|---:|
| 2024 primary | 2026-10-29 09:29:31.373655 to 09:29:42.596021 | `e7e90dc0188d3ceffbfaab40a96e5b6011b7ac16b4d4fed5b1330c72eca3401d` | 393,247 |
| 2025 confirmation | 2026-10-29 09:29:52.613565 to 09:30:01.169737 | `691e7530e6f55faf27e62659d31d3615f79c3b8b9dfa6fb4ac86d447a888d8c5` | 285,562 |

Both runs passed independent numerical validation. Maximum absolute errors were
2.62e-10 and 1.38e-10. The declared primary is the full-cross entry. The study
also retained separate midpoint and halfway fill sensitivities, reverse-entry
controls, and a no-trade zero control:

| Control or fill sensitivity | 2024 mean / median / win | 2025 mean / median / win |
|---|---:|---:|
| Midpoint expiry | +$61.70 / +$46.00 / 62.6% | +$43.06 / +$81.00 / 60.6% |
| Halfway expiry | +$51.39 / +$37.50 / 61.0% | +$30.75 / +$66.50 / 60.6% |
| Reverse intrinsic | -$82.32 / -$70.00 / 30.3% | -$67.66 / -$102.00 / 29.1% |
| Reverse close mark | -$82.32 / -$70.00 / 30.3% | -$67.66 / -$102.00 / 29.1% |
| No-trade zero | $0.00 / $0.00 / 0.0% | $0.00 / $0.00 / 0.0% |

Midpoint and halfway use their own retained ledgers. Each reverse control uses
its own reverse entry credit. The reverse physical-delivery next-open ledger
was not defined and is not reported. These comparisons follow the declared
frozen protocol, whose SHA-256 is
`952969cade05ec3e8b0c5ce388e8fac12a5ec9b0e823fa3160eb25f50dd5c662`; the input
manifest SHA-256 is
`75515e7ab8b748d9f3e4502a4adaf6bf7786e88a00da46c27070080976925cf0`. The
reviewed aggregate output SHA-256 is
`e86e6daae53440b481b92851083eef18bc4ed7ed7b87b45e37b77b8365f7873b`. The
evidence report identifies a preparation manifest that indexes the run outputs,
but does not state that manifest's hash, so no index hash is asserted here.

Entry quotes were timestamped at 15:59 ET while close references came later.
This timing gap matters for the 2024 and 2025 OptionMetrics study. Quote sizes,
fills and capacity were unavailable. The historical runs and their private
receipts are not included here. A public rerun is **NOT RUN** and cannot be
reconstructed without licensed exports and frozen control receipts.
