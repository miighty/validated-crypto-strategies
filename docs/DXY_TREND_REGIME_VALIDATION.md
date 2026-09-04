# US Dollar Index (DXY) Weakening Regime Filter Validation

Run: `python3 scripts/dxy_trend_regime_validation.py`
Artifact: `results/dxy_trend_regime/runs/run-20260904T020534Z/`

## Hypothesis

First genuinely **external, non-crypto-derived macro signal** tested in this
program. Real FRED `DTWEXBGS` (Nominal Broad U.S. Dollar Index, daily,
2006-01-02 onward). Fast 20d SMA < slow 60d SMA ("dollar weakening") should
precede crypto risk-on price action -- the classic macro "weak dollar -> risk
assets rally" thesis. Long BTC/ETH/SOL/XRP independently while regime on,
one full day publication/execution lag, 30bps round-trip cost.

## Result

| Asset | Blocks | Primary final ($1 start) | B&H final | Momentum ctrl | Random ctrl | Concentration | Test partition |
|---|---:|---:|---:|---:|---:|---:|---|
| BTC | 4 | 0.44x | 4.77x | 13.70x | 18.06x | 378% (fails) | loses (1.39x vs 3.84x) |
| ETH | 4 | 0.19x | 2.51x | 16.91x | 3.55x | 0.75% | loses (1.11x vs 1.58x) |
| SOL | 3 | 3.52x | 22.50x | 81.66x | 0.96x | 106% (fails) | loses (2.76x vs 7.43x) |
| XRP | 4 | 0.06x | 1.20x | 5.64x | 1.36x | 42% (fails) | loses (0.46x vs 3.15x) |

- 0/4 beat buy-and-hold, 0/4 beat the naive BTC-momentum control, 1/4 beat
  its own random-regime control (SOL only).
- 0/4 survive doubled cost or best-block exclusion; 0/4 clear the 20%
  concentration cap.
- 0/4 pass the untouched test partition (2023+).
- Only 3-4 regime blocks per asset over the full multi-year sample -- the
  20d/60d DXY SMA crossover is extremely low-frequency, so most of each
  asset's history sits in one or two very long blocks, and BTC/ETH/XRP all
  lose absolute capital outright in the "dollar weakening" regime.

## Verdict: REJECTED (decisive)

The dollar-weakening regime performed **worse than a coin flip** for crypto
in this sample -- BTC/ETH/XRP all lost real capital while "risk-on" by this
definition was supposedly active, and momentum/random controls beat the
primary rule on every asset. The classic macro weak-dollar-tailwind
narrative does not hold up as a simple SMA-crossover regime filter on
crypto spot returns over 2018-2026. This may reflect DXY's low-frequency,
slow-decision nature (few, long regime blocks -> effectively testing only
3-4 independent multi-year "bets" per asset, a genuinely thin sample) rather
than disproof of any dollar-crypto relationship at a different timescale --
but as specified, the rule is a clear reject.

## Do not retest

This exact 20d/60d DTWEXBGS regime construction on this universe. If
revisited, would need either a fundamentally shorter/faster DXY signal
(defeats the "slow structural macro filter" rationale), a level-based
z-score trigger instead of a crossover, or joint conditioning with a
crypto-specific confirmation signal -- not a plain SMA retune.
