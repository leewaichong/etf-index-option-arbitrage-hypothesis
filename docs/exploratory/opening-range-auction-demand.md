<!-- source: round125/R125-01/result.json, round103/R103-01/result.json -->

# Opening range and Treasury auction demand

## Question

Do two simple timing rules on the same ETFs, an opening-range breakout and a trade keyed to Treasury auction demand, hold up after costs?

## What ran

These two do not test the options gap. They check whether the ETF price data supports any easy timing effect.

- R125-01, run on 17 October 2026, trades a breakout of the first 30 minutes on public 1-minute bars for 10 ETFs, with a 1 bp cost. Each ETF has 2,521 bars, 2,520 for EEM, and the last 757 or 756 bars are held out untouched.
- R103-01, run on 17 October 2026, takes public Treasury auction results for the 10-year note and 30-year bond and trades IEF and TLT around them, at 5 and 10 bp cost, with a 70/30 split in time order.

## What it found

R125-01 is unclear. The annualised Sharpe ratios swing between large positive and large negative values across ETFs and between the full and held-out windows. 2,521 minute bars is only a few trading days, and annualising that inflates the ratios, so they are left out here.

Only the TLT leg of R103-01 ran. The 10-year leg failed because its IEF price file was missing, so it has no result. The 30-year leg covered 92 auctions. The rule goes long TLT after an auction whose bid-to-cover ratio beats the median, 2.31, goes short otherwise, and holds until the next auction. Recorded position turnover was 5 in each window.

| Window | Cost | Annualised return | Sharpe | Daily hit rate |
|---|---|---|---|---|
| In sample | 5 bp | -0.068 | -0.58 | 0.48 |
| In sample | 10 bp | -0.070 | -0.60 | 0.48 |
| Out of sample | 5 bp | -0.058 | -0.59 | 0.45 |
| Out of sample | 10 bp | -0.062 | -0.63 | 0.45 |

The TLT rule lost money in both windows at both costs.

## Caveats

- The position changed only a handful of times per window, so the auction result rests on very few switches.
- The opening-range run covers only a few trading days of minute data. Its numbers should not be quoted.
- Neither run touches option prices.

R125-01 and the TLT price bars in R103-01 come from Yahoo Finance. The auction results come from the U.S. Treasury.

Source: Yahoo Finance (https://finance.yahoo.com)

Source: U.S. Treasury Fiscal Data (https://fiscaldata.treasury.gov)

## Status

EXPLORATORY, not preregistered unless stated, not evaluated.
