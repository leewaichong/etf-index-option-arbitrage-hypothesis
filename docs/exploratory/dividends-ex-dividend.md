<!-- source: round70/R70-02/result.json, round81/R81-01/result.json, round81/R81-02/result.json -->

# Dividends and ex-dividend days

## Question

Could ETF dividends account for part of the gap, and do ETF prices behave oddly on ex-dividend days?

## What ran

Three runs on 17 October 2026 on public daily data.

- R70-02 sums the trailing dividend events for SPY, QQQ, IWM, TLT and GLD and divides by the latest close to get a trailing yield.
- R81-01 counts dividend events over two years for 10 ETFs.
- R81-02 compares the mean close-to-close return on ex-dividend days with the mean on all other days, and splits the events 70/30 in time order.

## What it found

Trailing dividend yield from R70-02.

| ETF | Events | Trailing yield |
|---|---|---|
| SPY | 4 | 0.0099 |
| QQQ | 4 | 0.0044 |
| IWM | 4 | 0.0101 |
| TLT | 12 | 0.0486 |
| GLD | 0 | 0 |

R81-02 mean returns. The events column matches the two-year counts from R81-01. The difference column is the ex-dividend mean minus the mean on other days.

| ETF | Events | Ex-div mean | Other days mean | Difference | Later 30% ex-div mean |
|---|---|---|---|---|---|
| SPY | 8 | -0.0002 | 0.0006 | -0.0008 | -0.0035 |
| QQQ | 8 | 0.0100 | 0.0007 | 0.0094 | 0.0114 |
| IWM | 8 | -0.0035 | 0.0005 | -0.0040 | 0.0002 |
| TLT | 24 | -0.0053 | -0.00004 | -0.0052 | -0.0052 |
| XLF | 8 | 0.0040 | 0.0003 | 0.0037 | 0.0023 |
| XLE | 8 | -0.0072 | 0.0011 | -0.0083 | -0.0060 |
| SMH | 2 | 0.0183 | 0.0018 | 0.0165 | 0.0097 |
| GDX | 2 | 0.0090 | 0.0019 | 0.0072 | 0.0272 |
| EEM | 4 | -0.0023 | 0.0008 | -0.0031 | 0.0036 |
| EFA | 4 | -0.0149 | 0.0007 | -0.0156 | -0.0157 |

Six of the ten ETFs return less on ex-dividend days than on other days. The sign of the ex-dividend mean flips between the earlier 70% and later 30% of events for SPY, IWM, GDX and EEM. With 2 to 24 events per ETF, the result is unclear.

## Caveats

- Returns come from the close price series. If that series is not adjusted for dividends, part of any ex-dividend drop is just the payout leaving the price.
- Two events for SMH and GDX is too few to say anything.
- No run here computed the dividend term in an ETF versus index option basis, so the link to the gap is untested. R70-02 only measures the yields.

Source: Yahoo Finance (https://finance.yahoo.com)

## Status

EXPLORATORY, not preregistered unless stated, not evaluated.
