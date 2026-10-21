<!-- source: round18/R18-04/result.json -->

# Smile, skew, premium and volume probe

## Question

Do SPY and SPX short-expiry options show a different volatility smile, and is volume concentrated in cheap contracts the way a speculator story would predict?

## What ran

R18-04 ran on 17 October 2026 on a retained Cboe delayed snapshot of the SPY and SPX chains captured on 16 October 2026 after the close. It groups short-expiry options by absolute delta band and type and takes median IV, mid price and volume. It also correlates premium per contract with volume, over 1,188 SPY and 1,932 SPXW contracts.

## What it found

Median IV by delta band, in decimals.

| Delta band | Type | SPY count | SPY IV | SPX count | SPX IV |
|---|---|---|---|---|---|
| 0.0-0.2 | call | 271 | 0.163 | 335 | 0.120 |
| 0.0-0.2 | put | 246 | 0.395 | 478 | 0.307 |
| 0.2-0.5 | call | 30 | 0.117 | 61 | 0.115 |
| 0.2-0.5 | put | 46 | 0.147 | 92 | 0.145 |
| 0.5-0.8 | call | 47 | 0.145 | 92 | 0.144 |
| 0.5-0.8 | put | 30 | 0.119 | 61 | 0.116 |
| 0.8-1.0 | call | 189 | 0.277 | 478 | 0.310 |
| 0.8-1.0 | put | 211 | 0.241 | 118 | 0.104 |

Near the money, in the 0.2 to 0.8 bands, SPY and SPX medians nearly match. The wide differences sit in the wings, where SPY low-delta puts and calls both carry higher median IV than SPX.

Premium per contract and volume correlate at -0.18 for SPY and -0.12 for SPXW. Median premium was 433.5 USD for SPY and 4,357.5 USD for SPXW, with median volume of 50.5 and 20.

Cheaper contracts trade a little more, but the link is weak. Whether that reflects speculation is unclear.

## Caveats

- SPY low-delta calls have a median mid of 0.005, and IVs backed out of prices that small are noisy. Deep in-the-money IVs are unreliable too, so read the 0.0-0.2 and 0.8-1.0 rows loosely.
- An SPXW contract carries far more notional than a SPY contract, so raw volume is not comparable across the two.
- This is one snapshot with delayed volume, and it shows no order flow.
- The pair construction behind these snapshot numbers was not re-verified against the matched-moneyness rule in the main README. The pattern of positive call credit and negative put credit resembles the strike-offset artefact the README describes, so treat the credit figures as descriptive of how the pairs were built, not as evidence of a mispricing.

Source: Cboe delayed quotes

## Status

EXPLORATORY, not preregistered unless stated, not evaluated.
