<!-- source: round64/R64-02/result.json, round65/R65-01/result.json, round69/R69-01/result.json -->

# Implied versus realised volatility

## Question

Do ETF options carry more implied volatility over realised volatility than the matching index options, and how big is the usual variance premium?

## What ran

Three runs on 17 October 2026.

- R64-02 takes the median implied volatility over every retained option row expiring within 3 days, for each ETF and index separately with no matching, from Cboe delayed snapshots. It subtracts 20-day realised volatility computed from public daily history. The file does not record the row count.
- R65-01 runs a similar comparison over matched ETF/index rows only, 307 for SPY/SPX, 140 for IWM/RUT and 847 for QQQ/NDX.
- R69-01 compares VIX with 5, 10, 20 and 60-day realised volatility for SPY, QQQ, IWM, TLT and GLD, over 251 daily rows per symbol.

## What it found

All values are decimals, so 0.01 is one volatility point. R64-02 uses unmatched short-expiry rows and R65-01 uses matched rows, so their median IVs are not comparable.

| Pair | Run | ETF IV | Index IV | ETF IV minus RV | Index IV minus RV | ETF minus index IV |
|---|---|---|---|---|---|---|
| SPY/SPX | R64-02, unmatched | 0.205 | 0.186 | 0.100 | 0.082 | 0.0186 |
| SPY/SPX | R65-01, matched | 0.1345 | 0.1314 | 0.0298 | 0.0268 | 0.0024 |
| IWM/RUT | R64-02, unmatched | 0.310 | 0.303 | 0.163 | 0.160 | 0.0063 |
| IWM/RUT | R65-01, matched | 0.1681 | 0.1673 | 0.0215 | 0.0237 | 0.0025 |
| QQQ/NDX | R64-02, unmatched | 0.256 | 0.237 | 0.072 | 0.051 | 0.0191 |
| QQQ/NDX | R65-01, matched | 0.2164 | 0.2154 | 0.0331 | 0.0296 | 0.0018 |

On matched rows the ETF sits above the index by 0.0018 to 0.0025 in all three pairs. On unmatched rows the gap is larger, but those rows differ by strike and expiry.

R69-01 puts SPY 20-day realised volatility at 0.105. The file records VIX minus 20-day RV as 0.095 for SPY, 0.017 for QQQ, 0.053 for IWM, 0.087 for TLT and -0.011 for GLD.

## Caveats

- Realised volatility is one 20-day window, so the IV minus RV numbers are a single reading.
- The matched-row result is the fairer comparison. The unmatched result mixes different strikes and expiries on each side.
- VIX is implied volatility on the S&P 500. Comparing it with QQQ, IWM, TLT or GLD realised volatility mixes different assets, so only the SPY row is a like-for-like premium.
- The pair construction behind these snapshot numbers was not re-verified against the matched-moneyness rule in the main README. The pattern of positive call credit and negative put credit resembles the strike-offset artefact the README describes, so treat the credit figures as descriptive of how the pairs were built, not as evidence of a mispricing.
- None of this is a tradable edge on its own.

Option IV comes from Cboe. Realised volatility and VIX come from Yahoo Finance.

Source: Cboe delayed quotes

Source: Yahoo Finance (https://finance.yahoo.com)

## Status

EXPLORATORY, not preregistered unless stated, not evaluated.
