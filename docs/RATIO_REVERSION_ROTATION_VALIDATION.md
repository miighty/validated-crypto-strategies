# Alt/BTC Ratio Mean-Reversion Rotation Validation

## Hypothesis (preregistered)

A single long-only capital sleeve rotates 100% into an altcoin when its BTC-ratio
z-score (60d rolling, shift(1), no lookahead) is deeply negative (alt "cheap" vs
BTC, z <= -1.0) and 100% into BTC when deeply positive (alt "expensive" vs BTC,
z >= +1.0), holding position otherwise (hysteresis band). Mechanistically distinct
from every prior study in this repo: not a dollar-neutral cross-sectional L/S
(Amihud/funding-carry/momentum/vol-premium, all REJECTED), not a calendar effect,
not a trend filter, not an event-odds/sentiment contrarian rule. Tested
independently on ETH/BTC, SOL/BTC, XRP/BTC using real cached Binance spot daily
OHLCV (`data/raw/{ETH,SOL,XRP,BTC}_1d.csv.gz`), full history through 2026-07-27.

Fastest rejection criterion (preregistered): must beat both legs' buy-and-hold
AND a static 50/50 no-rebalance blend on the full sample after 30bps round-trip
costs, survive doubled costs, stay under the 20% single-trade concentration cap,
and log >=5 trades in the test partition (2024-07-01 onward).

## Result

| Pair | Trades (total/test) | Strategy final ($10k start) | BH alt | BH BTC | Static 50/50 blend | Doubled cost | Random-flip control | Concentration |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ETH/BTC | 54 / 12 | $24,685 | $22,235 | $74,708 | $48,472 | $20,986 | $87,807 | 147% |
| SOL/BTC | 34 / 13 | $17,047 | $259,187 | $58,383 | $158,785 | $15,391 | $146,074 | 193% |
| XRP/BTC | 45 / 14 | $27,676 | $20,168 | $101,316 | $60,742 | $24,173 | $39,425 | 136% |

- Beats own-leg buy-and-hold on only 2/3 pairs (ETH, XRP) — loses to SOL/USDT buy-and-hold badly.
- **Loses to BTC buy-and-hold on all 3 pairs** — decisive, since BTC was the strategy's own alternate leg.
- **Loses to the static 50/50 no-rebalance blend on all 3 pairs.**
- **Loses to its own seeded random-flip control on all 3 pairs** (same trade count/cost structure) — the timing signal has zero or negative value versus randomly choosing when to flip.
- **Concentration cap badly violated on all 3 pairs** (136–193%, meaning the single largest trade block's magnitude *exceeds* total net strategy PnL — the rest of the trades are net losers).
- Survives doubled cost only in the trivial sense of still beating $10,000 cash; does not change the verdict.

## Verdict: REJECTED (decisive)

Every pair fails the primary preregistered gate (beat both legs' B&H + static blend)
and additionally fails the harder falsification bars (random-flip control,
concentration cap). The z-score ratio signal carries no genuine timing value on
this frame/window — it is dominated by simply holding either leg statically, and
the strategy's apparent profitability versus cash is explained entirely by one or
two lucky flip windows per pair (concentration >100%), not a repeatable
mean-reversion edge.

## Files

- `scripts/ratio_reversion_rotation.py`
- `results/ratio_reversion_rotation/summary.csv`
- `results/ratio_reversion_rotation/trades_{ETH,SOL,XRP}.csv`
