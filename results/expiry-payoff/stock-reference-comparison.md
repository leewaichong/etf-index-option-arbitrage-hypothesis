# Legacy stock-reference comparison

**Status: EVALUATED before this public source export.** The five-arm comparison
ran on clean commit `ac0b05e3bce2d6c4a176bb49a392f47ae2912306`. This is a fixed
2019/2022 historical sensitivity using retained option contracts. It is separate
from the 2024/2025 OptionMetrics study and does not evaluate the public port.

The frozen comparison changed stock-reference inputs while holding option
quotes, contracts, entry cash and settlement fixed. It used one-calendar-day DTE,
three distinct fill ledgers, midpoint, halfway and full-cross, 100 multipliers,
and a 10-short-SPY / 1-long-SPXW package. Full-cross was primary. Results for
different fills are kept separate; their denominators are not pooled.

The table reports hypothetical package cash P&L in USD. The full-cross base-cost
column is the modeled cost ledger for selling 10 SPY and buying 1 SPXW. The
stock-neutralized column removes the modeled overnight stock-price contribution.
Neither column is an account return.

| Period | n | Full-cross all-WRDS base-cost mean | Descriptive 95% interval | Stock-neutralized accounting mean | Descriptive 95% interval |
|---|---:|---:|---:|---:|---:|
| 2019 pilot | 9 | -$817.49 | Not estimated | Not reported | Not estimated |
| 2022 | 63 | +$114.07 | [-$146.12, +$367.51] | -$50.46 | [-$99.29, -$9.93] |

In 2022, all five arms had identical P&L and no modeled assignment flips. The
2019 full-cross all-WRDS base-cost mean changed by +$0.0016 from its baseline;
the pilot has descriptive means only. The 2022 ex-dividend zero sensitivity
reflects no eligible assigned carry interval crossing the event. Changing the
stock source does not identify which provider is correct.

The comparison protocol SHA-256 is
`4c95d681bd802bc4dcde657e2b9ddb3a0e7578f0cdf45d6015e7e024fd934a8b`; the input
manifest SHA-256 is
`348d6fb3cb1cf1a93566dd41bea14a73e62df40195a2e2494cdf483dae72baa6`. The
selected snapshot SHA-256 is
`335a0266a9c556d97bf7ecb26c7e7f9691273aa253d133e973032a11513300ac`. The final
evaluation manifest SHA-256 is
`7617d4866f05317a7ab9cb871e45cbf86ac4367f27c6ec1d63026869de8011a8`. Evaluation
ran 2026-10-29 14:25:26.486366 to 14:26:39.374681 UTC. Independent checks passed
135,802 checks for the five-arm evaluation and 5,601 for legacy baseline
summaries, 141,403 combined, with maximum absolute error 3.18e-12. The declared
control was the retained baseline stock references; the five arms were compared
against it with frozen option inputs.

The evaluated run and independent validation index was SHA-256
`16c6c93b68bb87013386f4bd2833271b76d3275f834c74dd901492d515b2ae92`. The
approved aggregate PDF SHA-256 is
`d8cabef549c033672e0e6052ad4ed5244eac3ba0d0314fee8889eb11e8d15363`. The
PDF’s extracted text was checked for private paths and email addresses before
publication.

No dependable executable edge was established. Assignment, fills, capacity,
margin and funding remain unobserved. Legacy quote clocks are unresolved. The
samples were previously inspected and are not untouched holdouts. A public
historical rerun is **NOT RUN** and lacks the licensed exports and private
frozen-control receipts.
