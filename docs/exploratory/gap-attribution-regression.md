<!-- source: round19/R19-04/result.json, round20/R20-01/result.json, round22/R22-02/result.json -->

# Gap attribution regression

## Question

Which observable features of a short-expiry SPY/SPX pair line up with the executable credit, and what drives option spreads across tickers?

## What ran

Three descriptive runs on 17 October 2026, all on retained Cboe delayed snapshots.

- R19-04 compares the SPY minus SPX implied volatility difference with executable credit, by expiry bucket and option type, over the same 301 matched short-expiry pairs used in the zero-day probe.
- R20-01 regresses executable credit on volume, open interest, IV difference, absolute SPY delta, a call flag and expiry flags. It has 301 rows.
- R22-02 regresses relative bid-ask spread on log mid price, absolute delta, log volume and an index-root flag. It has 8,246 rows across 16 symbols from snapshots filed under sessions 2026-10-15 and 2026-10-19.

## What it found

R19-04 shows the IV difference tracks credit for calls and much less for puts. IV is in decimal units, so 0.01 is one volatility point.

| Bucket | Type | Pairs | Median IV difference | Correlation with credit |
|---|---|---|---|---|
| 0DTE | call | 27 | 0.0033 | 0.78 |
| 0DTE | put | 28 | 0.0016 | 0.26 |
| 1DTE | call | 35 | 0.0029 | 0.45 |
| 1DTE | put | 34 | 0.0016 | 0.22 |
| 2-3DTE | call | 87 | 0.0022 | 0.70 |
| 2-3DTE | put | 90 | 0.0023 | -0.13 |

R20-01 has an R-squared of 0.757 on 301 rows.

| Term | Coefficient |
|---|---|
| intercept | 11.47 |
| log SPY volume | -0.80 |
| log SPX volume | 0.53 |
| log SPY open interest | -0.98 |
| log SPX open interest | -0.37 |
| IV difference | 518.46 |
| absolute SPY delta | -11.21 |
| call | 3.81 |
| 0DTE | 3.77 |
| 1DTE | 1.77 |

The file has no standard errors, so none of these coefficients can be called significant.

R22-02 has an R-squared of 0.383. Relative spread falls with log mid price at -0.043, with absolute delta at -0.47 and with log volume at -0.070. The index-root coefficient came out as exactly 0.0, so the regression did not estimate an index-versus-ETF spread effect.

## Caveats

- These are cross-sections from snapshots, not time series. They describe, they do not explain.
- R20-01 drops the premium ratio because it is built from the same prices as the response. The remaining features are correlated with each other, so single coefficients are unstable and not causal.
- The model cannot identify who is trading. It says nothing about speculators directly.
- R22-02 leaves symbol and session differences in the error term.
- The pair construction behind these snapshot numbers was not re-verified against the matched-moneyness rule in the main README. The pattern of positive call credit and negative put credit resembles the strike-offset artefact the README describes, so treat the credit figures as descriptive of how the pairs were built, not as evidence of a mispricing.

Source: Cboe delayed quotes

## Status

EXPLORATORY, not preregistered unless stated, not evaluated.
