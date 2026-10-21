# Does the index-versus-ETF option gap survive matched moneyness?

**Short answer: no.** Three independent datasets, 46,553 matched pairs, and the gap at
equal moneyness is well under one basis point — far smaller than the cost of crossing
either leg. This repository contains the measurement code, the rule that
was fixed before the data was opened, and the aggregate results.

---

## Why test this idea in plain words

SPY is an ETF that holds the S&P 500. SPX options are options on the index itself.
Both give you exposure to the same 500 companies, so a call on SPY and a call on the
index with the same expiry and the same moneyness should cost about the same. If one
side is persistently more expensive — beyond what it costs to trade — that is an
arbitrage-style edge: sell the rich leg, hold the cheap one, and collect the
difference as the prices converge.

The catch is that "the same strike" is not "the same moneyness". The index trades
around ten times the ETF's price, so an index option at strike 4000 and an ETF option
at strike 400 are not the same contract at all — one is at the money, the other is
deep out of it. This repository exists to make that comparison correctly, and then to
report honestly whether anything survives.

## Method

1. **Match on moneyness, not strike.** For an ETF strike `K`, the matching index
   strike is `round(K × ratio)`, where `ratio` is the index forward divided by the
   ETF forward, both taken from put-call parity on the same snapshot.
2. **Match the expiry exactly.** A pair must share one expiry date.
3. **Use one timestamp.** Both legs must come from the same daily close or the same
   snapshot, otherwise you are subtracting two different market states.
4. **Cohort by expiry.** One cohort is one expiry date; all pairs sharing it are
   summarised by their median gap in basis points of the ETF strike.
5. **Drop bad quotes rather than repairing them.** Zero-bid, one-sided or crossed
   quotes are removed; a zero bid is not a price.

### The rule, fixed before the data was opened

| test | threshold |
|---|---|
| effect size | median matched gap **≥ 2.0 bps** |
| stability | same sign in **≥ 60%** of cohorts |
| null band | median within **±1.0 bps** of zero |
| coverage | at least **8 cohorts**, at least 8 strikes per cohort |

A result above the effect threshold *and* consistent in sign would be worth
designing a trade around. A result inside the null band is not supported. Anything
between is inconclusive. These numbers were not adjusted after seeing results.

## What went wrong first

Three mistakes, each of which produced a number that looked like a real effect:

- **The same-strike artefact.** Comparing options at identical strikes produced gaps
  of **19–24 bps**. That was wrong: comparing at the same strike put the two legs at
  different moneyness, because the two instruments do not trade at the same price.
  Matching on moneyness removed the effect, and the gap fell below one basis point.
  This was the single biggest error and it is what motivated the whole method here —
  `tests/` contains a test that reproduces it on synthetic data.
- **Snapshot skew.** Pulling each leg from a separately cached source gave quotes
  minutes apart. Refetching did not help: the timestamps were frozen and did not
  advance at all across repeated requests. For a sub-basis-point effect, two
  different minutes are not a measurement.
- **Opening-auction quotes.** The first prints of a session are the least settled of
  the day, and they exaggerated the gap by roughly ten times versus the same
  instruments later in the session.

## Results

Three datasets, different vendors and different years. All aggregate; no raw data is
included.

| dataset | period | matched pairs | cohorts | median matched gap | verdict |
|---|---|---:|---:|---:|---|
| ETF vs index, end-of-day panel | 2026 | 582 | 12 | **−0.39 bps** | not supported |
| ETF vs index proxy, end-of-day panel | 2026 | 58 | 2 | **−0.60 bps** | not supported |
| **Free end-of-day sample, ETF vs index** | **2022 H2** | **45,913** | **94** | **−0.13 bps** | **not supported** |

The 2022 sample is the strongest test: 94 expiry cohorts over 127 trading days, both
legs from one daily close, on a different vendor and in a different volatility
regime. Its median is **fifteen times smaller** than the effect threshold, and 62 of
94 cohorts were negative against 32 positive.

Cohort-level medians for the 2022 sample are in `results/cohort_2022h2.csv`. **That
CSV contains only per-expiry aggregate medians** (expiry date, pair count and median
gap, three columns) derived from the source credited below. The two 2026 rows are
given as summary figures in the table only, with no file, because that vendor's terms
allow aggregated statistics but not machine-readable files of its data. No row-level
or raw option data is included anywhere in this repository.

### Caveats

- **2022 was a different regime.** Higher rates and higher volatility than today.
  Agreement across regimes strengthens the negative result; a positive result there
  would not have licensed a trade today.
- **No within-day timestamps** in the 2022 sample, so stale quotes cannot be filtered
  out. That adds noise in both directions.
- **Cohorts are not independent.** Each expiry appears on several consecutive
  sessions, so the effective sample is nearer 94 than 45,913. Nothing here is offered
  as statistical inference.
- **Pre-registration timing, honestly.** The rule was written down before the 2022
  data was opened, but the two 2026 panels had already been looked at in earlier
  work. For those panels the threshold is applied post hoc; the 2022 result is the
  genuine out-of-sample test.

## Conclusion: not supported

At matched moneyness, the gap between an ETF option and the corresponding index
option is **well under one basis point** across all three datasets (−0.13 to
−0.60 bps). Crossing a single leg costs on the order of 0.5 bps, so there is no version of this trade that pays for its own execution, let
alone one that produces a persistent arbitrage.

The sign is mildly sticky — about two thirds of cohorts share a direction — but
stickiness without magnitude is not an edge.

**What would change the answer:** a dataset that clears a median of 2 bps or more in
a consistent direction across at least 8 expiry cohorts, measured on both legs at a
single timestamp. That is a well-defined bar; nothing tested so far has come within
an order of magnitude of it.

## Reproduce it yourself

```bash
python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt

# unit tests (synthetic fixtures, no data, no network)
.venv/bin/python -m pytest tests -q

# apply the rule to your own cohort table
.venv/bin/python - <<'PY'
import sys; sys.path.insert(0, "src")
import matched_moneyness as mm
table = mm.cohort_summary({"2022-08-19": [0.2, -0.1, 0.4] * 5, "2022-08-26": [0.1] * 20})
print(mm.verdict(table))
PY
```

To measure your own pair you need option quotes for both legs at **one timestamp**,
with bid and ask, expiry, strike and side. Build chains with
`mm.build_chain(rows)`, then call `mm.matched_gap(etf_chain, index_chain, expiry)`.

### Where to get free data

- **[HistoricalData.net](https://historicaldata.net/options.html)** — free end-of-day
  option sample (SPY and SPX/SPXW, July to December 2022) with a documented schema,
  one close per day. The 2022 H2 result above is computed from it. Its licence allows
  publishing statistics but not the data, so none of the data is included here.
  Download it yourself and read their licence.
- **Source: Market Data ([https://www.marketdata.app](https://www.marketdata.app))** —
  free-tier end-of-day option quotes (24-hour delayed, up to a year of history). The
  two 2026 rows in the results table are aggregate statistics derived from it. No
  data from this source is included; see their
  [terms](https://www.marketdata.app/terms/public-use/).
- **Cboe delayed quotes** — free delayed option chain snapshots:
  `https://cdn.cboe.com/api/global/delayed_quotes/options/SYMBOL.json`, with index
  roots prefixed by an underscore (`_SPX`, `_XSP`, `_NDX`, `_RUT`). Delayed, snapshot
  only, and **cached per root** — the timestamps of two roots can be minutes apart,
  which makes it unsuitable for a two-leg comparison without checking staleness.
  Review Cboe's terms before any automated use.

## Limitations

- Close-based prices are not executable; a gap measured at the close says nothing
  about what you could have traded.
- The method compares mid prices. A real trade crosses the spread, which is larger
  than the effect being measured.
- Only calls were used; a put-side test would be a useful independent check.
- Results are sensitive to how the moneyness ratio is estimated. Using parity
  forwards on a tight near-the-money window avoids the far-out-of-the-money quotes
  that distort the estimate, but it is still an estimate.
- Nothing here accounts for borrow, financing, dividends or settlement mechanics.

## Video and diagram

A 90-second narrated explainer of why this idea was tested and what came out:
[`assets/opt-gap-explainer.mp4`](assets/opt-gap-explainer.mp4).

![The two-basis-point bar against the measured gap](assets/opt-gap-diagram.png)

## Licence

MIT — see `LICENSE`.
