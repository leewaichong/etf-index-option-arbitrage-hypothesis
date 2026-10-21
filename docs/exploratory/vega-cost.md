<!-- source: round65/R65-02/result.json, round68/R68-02/result.json -->

# Vega cost

## Question

How far would implied volatility have to move before a matched ETF/index option pair covers its spreads and fees?

## What ran

Two runs on 17 October 2026 on retained Cboe delayed snapshots. The SPY/SPX pairs come from a snapshot captured on 16 October 2026 after the close. The IWM/RUT and QQQ/NDX pairs come from snapshots recorded on 17 October 2026. Each matched pair takes real bid-ask spreads, fees and the quoted vega, and solves for the break-even volatility move.

- R65-02 reports the median per index pair, over 307 SPY/SPX rows, 140 IWM/RUT rows and 847 QQQ/NDX rows.
- R68-02 splits the same rows by calls and puts.

## What it found

Median break-even move, in volatility points as the file records them.

| Pair | All rows | Calls | Puts |
|---|---|---|---|
| SPY/SPX | 0.155 | 0.170 | 0.152 |
| IWM/RUT | 0.584 | 0.585 | 0.573 |
| QQQ/NDX | 0.882 | 0.814 | 0.920 |

SPY/SPX is the cheapest pair to trade on this measure, by a wide margin. Calls and puts sit close together within each pair, so option type does not change the picture.

## Caveats

- This is a proxy. It uses quoted spreads and vega at one moment and does not model fills, hedging or how vega changes over the holding period.
- The pairs come from snapshots taken at different times, so the three rows are not a same-instant comparison.
- A low break-even says the pair is cheap to trade, not that the gap will move enough to pay.
- The pair construction behind these snapshot numbers was not re-verified against the matched-moneyness rule in the main README. The pattern of positive call credit and negative put credit resembles the strike-offset artefact the README describes, so treat the credit figures as descriptive of how the pairs were built, not as evidence of a mispricing.

Source: Cboe delayed quotes

## Status

EXPLORATORY, not preregistered unless stated, not evaluated.
