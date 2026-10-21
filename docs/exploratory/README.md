# Exploratory side ideas

These pages cover side ideas about why a gap between ETF and index options might exist. None of them changed the verdict. Each page reports only what its result file recorded, and each carries the same status line.

EXPLORATORY, not preregistered unless stated, not evaluated.

Most runs used retained Cboe delayed snapshots from October 2026, and the execution-cost surface and the speculator sweeps also include synthetic models with no market data. Each page names its source. Three further side ideas (implied against realised volatility, dividends, and ETF timing rules) are withheld until the terms of their public price-history source are checked.

- [Zero-day speculator inflation and decay](zero-day-speculator-sweeps.md) tests what cost an assumed speculator premium survives and whether the snapshot shows one.
- [Gap attribution regression](gap-attribution-regression.md) regresses executable credit and option spreads on volume, open interest, IV difference and delta.
- [Vega cost](vega-cost.md) measures the volatility move needed to cover spreads and fees, by pair and option type.
- [IV term gap](iv-term-gap.md) splits the ETF minus index IV gap by expiry bucket and option type.
- [Smile, skew, premium and volume probe](smile-skew-premium-volume.md) compares SPY and SPX IV by delta band and checks premium against volume.
- [Execution-cost surface](execution-cost-surface.md) finds the widest spread a given richness survives in a synthetic cost model.
- [Other ETF pairs on the same index](other-etf-pairs.md) screens SPY and IVV, QQQ and QQQM, GLD and IAU, IWM and VTWO for a same-feed test. All four failed on availability.
