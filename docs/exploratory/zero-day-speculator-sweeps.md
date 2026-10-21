<!-- source: round15/R15-03/result.json, round16/R16-02/result.json, round18/R18-02/result.json -->

# Zero-day speculator inflation and decay

## Question

If heavy zero-day buying inflates short-dated SPY option prices, how much trading cost could that premium absorb, and does the retained data show any sign of it?

## What ran

Three runs on 17 October 2026.

- R15-03 is a synthetic simulation with 500 paths of 5 periods each, 50,000 USD capital, a base inflation of 2.0 points that decays by 0.55 per period, and a cost grid from 0 to 800 USD per round trip. No market data went in.
- R16-02 repeats the sweep on 300 synthetic paths with three decay rates, 0.30, 0.55 and 0.80. No market data went in.
- R18-02 is a descriptive probe on 301 matched short-expiry SPY/SPX pairs from a retained Cboe delayed snapshot captured on 16 October 2026 after the close.

## What it found

The synthetic break-even cost is the largest tested grid point where mean net P&L stays positive.

| Inflation multiplier | R15-03 break-even, USD | R16-02 decay 0.30 | R16-02 decay 0.55 | R16-02 decay 0.80 |
|---|---|---|---|---|
| 0.5 | 75 | 50 | 75 | 75 |
| 1.0 | 150 | 150 | 150 | 150 |
| 2.0 | 300 | 300 | 300 | 300 |
| 4.0 | 600 | 600 | 600 | 600 |

Break-even scales with the assumed premium. Changing the decay rate only moved the smallest case.

In the real snapshot, executable credit per unit correlates with SPY open interest at -0.30 and with SPX open interest at -0.38. Its correlation with SPY volume is -0.11 and with the SPY/SPX volume ratio is -0.02. Credit does not rise with volume in this snapshot. Median executable credit per unit is positive for calls in every bucket and negative for puts in every bucket.

| Bucket | Type | Pairs | Median credit per unit | Median SPY/SPX volume ratio |
|---|---|---|---|---|
| 0DTE | call | 27 | 3.2 | 10.4 |
| 0DTE | put | 28 | -2.3 | 9.0 |
| 1DTE | call | 35 | 2.5 | 11.2 |
| 1DTE | put | 34 | -2.35 | 8.4 |
| 2-3DTE | call | 87 | 2.0 | 8.1 |
| 2-3DTE | put | 90 | -2.6 | 7.4 |

Whether speculators inflate prices stays unclear. The real data gives the story no support.

## Caveats

- The two sweeps assume the premium exists. They show what cost it would survive, not whether it is real.
- Break-even values come from a grid, so they are bounds, not exact roots.
- Volume and open interest in the snapshot are delayed fields from one moment. One snapshot cannot show order flow.
- The premium ratio correlates at 0.76 with credit, but the two are built from the same prices, so that number says nothing about cause.
- The pair construction behind these snapshot numbers was not re-verified against the matched-moneyness rule in the main README. The pattern of positive call credit and negative put credit resembles the strike-offset artefact the README describes, so treat the credit figures as descriptive of how the pairs were built, not as evidence of a mispricing.

R15-03 and R16-02 are synthetic and use no market data. R18-02 uses the retained snapshot.

Source: Cboe delayed quotes

## Status

EXPLORATORY, not preregistered unless stated, not evaluated.
