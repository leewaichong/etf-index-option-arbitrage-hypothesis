# Other ETF pairs on the same index

## Question

Would options on two ETFs that track the same index (SPY and IVV, QQQ and QQQM, GLD and IAU, IWM and VTWO) show the same kind of gap, with both legs coming from one data feed so the quotes are synchronised?

## What ran

A one-day availability screen on 21 October 2026, using the free paper-account options feed of one broker. It listed which contracts exist for each pair and looked at the quotes on the front expiries. No gap was computed.

## What it found

All four pairs failed before any comparison could start.

| Pair | Why it failed |
|---|---|
| SPY and IVV | IVV lists a single front expiry where SPY lists two, and its quotes are very wide |
| QQQ and QQQM | QQQM has no listed option contracts on this feed |
| GLD and IAU | IAU has a single expiry and very wide quotes, so there is no common expiry |
| IWM and VTWO | VTWO has no listed option contracts on this feed |

Even on one feed, the two legs' quote timestamps differed by more than a minute, so one feed did not give synchronised quotes either.

## Caveats

- The screening criteria were not written down before looking. The two hard failures (no contracts at all) need no threshold. The liquidity cut is a judgement made afterwards.
- One day and one feed. A different feed or day could list different contracts.
- This says the pairs cannot support the same test. It says nothing about whether those prices are consistent.

Source: Alpaca Markets paper-account options feed

## Status

EXPLORATORY, not preregistered, not evaluated.
