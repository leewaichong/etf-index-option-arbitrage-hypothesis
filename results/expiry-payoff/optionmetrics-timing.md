# OptionMetrics timing sensitivity

**Status: EVALUATED before this public source export.** The clean evaluated
commit was `d6eff1d112d83d9debaa8469d3812b478af70fd3`. This was an exploratory
sensitivity on known 2024 and January to August 2025 data, not a holdout and not
a test of the public source changes.

The study retained the same 195 2024 and 127 partial-2025 expiries in each lane.
For full-cross entry, the mean expiry intrinsic and base-cost P&L were:

| Period | Reference | Expiry intrinsic | Base cost |
|---|---|---:|---:|
| 2024 | Entry-session close | +$41.09 | -$476.37 |
| 2024 | Prior-session close | -$21.66 | -$372.41 |
| 2024 | Session open | +$22.90 | -$315.51 |
| 2025 Jan-Aug | Entry-session close | +$18.45 | +$224.27 |
| 2025 Jan-Aug | Prior-session close | -$13.05 | -$43.22 |
| 2025 Jan-Aug | Session open | +$74.00 | +$142.01 |

USD per hypothetical 10-short-SPY / 1-long-SPXW package, 100 multipliers and
equal expiry weights. The full-cross entry is SPY bid and SPXW ask. The shared
protocol SHA-256 is `e4ae0387236466fa1a69bfdc7e654501a4a6dde292077412e86f8199d052cae7`.
The input manifest SHA-256 is
`75515e7ab8b748d9f3e4502a4adaf6bf7786e88a00da46c27070080976925cf0`.
The comparison manifest SHA-256 is
`0464e6716d18e2715193c275017fb65fd0a90a8e57dbd2f3c39168a0e3dd7f8d`.
The reviewed aggregate SHA-256 is
`6f47398c9f89571778f8c05d1be5fa50ead8ddbf630b814cd16e11d82f921378`.
The 2024 selection snapshot SHA-256 is
`ee7b54f0c691d94fa69b23d6cf72fc54487fd1eec077c9bd1a12e459b3e354e0` and its
comparison output SHA-256 is
`685c95b0b4c7d6dfc9d740adb619405e2639405a960b4b04245b67cd03113ed4`. The 2025
selection snapshot SHA-256 is
`8b13c037fb1e3c2c92b033367da1f5d83520e36bf59516b113af189f998807cc`; its
comparison output SHA-256 is
`eea44586b9cd21417172ff48d9f2a46e8572288c9d64e3999a8470c630c9bff6`.

Evaluations ran on 2026-10-29 UTC. The 2024 run was 11:39:55.361746 to
11:40:20.846271; the 2025 run was 11:40:53.968502 to 11:41:09.600771.
Original-control parity passed for 585 selected fields and 3,319 aggregate
numeric fields in 2024, and 381 selected fields and 2,307 numeric fields in
2025. Independent validation passed 168,058 and 110,098 checks, respectively.
The declared control was the entry-session close lane; alternative lanes were
compared against it by expiry. No result establishes an executable edge.

The 15:59 ET BBO versus later close-reference caveat applies to this 2024/2025
OptionMetrics study. Historical quote-clock alignment for the legacy 2019/2022
comparison remains unresolved. Quote sizes, actual fills and capacity were
unavailable. These periods had previously inspected underlying and strategy
data. A public rerun is **NOT RUN**; the licensed inputs and frozen run controls
are unavailable in this checkout.
