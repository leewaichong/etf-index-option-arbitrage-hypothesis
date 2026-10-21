<!-- source: round67/R67-02/result.json -->

# IV term gap

## Question

Does the ETF minus index implied volatility gap change with days to expiry, and does it differ between calls and puts?

## What ran

R67-02 ran on 17 October 2026 on retained Cboe delayed snapshots captured on 16 and 17 October 2026. It takes the median IV in four expiry buckets for each side and subtracts. The file does not record row counts per bucket.

## What it found

ETF median IV minus index median IV, in decimals, so 0.01 is one volatility point.

| Pair | Bucket | Calls | Puts |
|---|---|---|---|
| SPY/SPX | 0DTE | -0.0417 | 0.0927 |
| SPY/SPX | 1DTE | -0.0226 | 0.0424 |
| SPY/SPX | 2-3DTE | -0.0116 | 0.0532 |
| SPY/SPX | 4-7DTE | -0.0126 | 0.0548 |
| IWM/RUT | 0DTE | 0.0416 | -0.0633 |
| IWM/RUT | 1DTE | 0.0111 | 0.0147 |
| IWM/RUT | 2-3DTE | -0.0150 | -0.0029 |
| IWM/RUT | 4-7DTE | 0.0515 | not usable |
| QQQ/NDX | 0DTE | 0.0990 | -0.1434 |
| QQQ/NDX | 1DTE | 0.0826 | -0.0369 |
| QQQ/NDX | 2-3DTE | 0.0466 | 0.0048 |
| QQQ/NDX | 4-7DTE | 0.0382 | -0.0304 |

For SPY/SPX the ETF puts sit above the index in every bucket and the ETF calls sit below. QQQ/NDX shows the opposite pattern at 0DTE and 1DTE. IWM/RUT has no consistent sign. Across the three pairs the term pattern is unclear.

## Caveats

- The IWM 4-7DTE put median IV is 0.0 in the file, which is not a real quote, so that cell is dropped.
- Bucket medians mix whatever strikes each side lists, so a skew difference can show up as a term gap.
- The snapshots were taken at different times, so the pairs are not a same-instant comparison.
- The pair construction behind these snapshot numbers was not re-verified against the matched-moneyness rule in the main README. The pattern of positive call credit and negative put credit resembles the strike-offset artefact the README describes, so treat the credit figures as descriptive of how the pairs were built, not as evidence of a mispricing.

Source: Cboe delayed quotes

## Status

EXPLORATORY, not preregistered unless stated, not evaluated.
