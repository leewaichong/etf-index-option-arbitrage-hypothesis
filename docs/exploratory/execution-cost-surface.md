<!-- source: round20/R20-02/result.json -->

# Execution-cost surface

## Question

For a given SPY richness over SPX, how wide can the bid-ask spread get before a paired trade stops netting a profit?

## What ran

R20-02 ran on 17 October 2026 as a synthetic sensitivity model with no market data. It crosses richness of 0.5, 1, 2 and 4 points with spreads of 0.1, 0.25, 0.5, 1 and 2 points, SPY quantities of 1, 5 and 10, and holding periods of 0 and 1 day, for 120 rows. Fixed assumptions are a SPY premium of 3.0 points, an SPX premium of 30.0 points, a SPY strike of 760, a capital fraction of 0.2, 8% annual financing and a published retail broker fee schedule.

## What it found

The break-even spread is the widest tested spread with positive net.

| Richness, points | Break-even spread, points | Best case quantity | Best case holding days | Beyond tested grid |
|---|---|---|---|---|
| 0.5 | 0.25 | 1 | 0 | no |
| 1.0 | 0.5 | 1 | 0 | no |
| 2.0 | 1.0 | 1 | 0 | no |
| 4.0 | 2.0 | 1 | 0 | yes |

Break-even spread rises with richness, and in every case the best result came from one contract closed the same day. At 4 points of richness the true break-even may lie above the widest spread tested.

## Caveats

- The richness levels are assumed. The model says what a premium of a given size would survive, not that one exists.
- Break-even values are grid points, not exact roots.
- This is a cost model. It does not simulate fills or P&L.

The model uses no market data.

## Status

EXPLORATORY, not preregistered unless stated, not evaluated.
