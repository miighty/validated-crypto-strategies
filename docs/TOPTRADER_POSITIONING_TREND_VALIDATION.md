# Top-Trader Positioning Trend (SMA10/SMA30) Regime Filter Validation

Run artifact: `results/toptrader_positioning_trend/runs/run-20260902T013540Z/`

## Hypothesis

Binance's public futures metrics archive discloses the "top trader" account
long/short position ratio (`sum_toptrader_long_short_ratio`) — the aggregate
positioning of the exchange's largest, best-capitalized accounts — distinct
from `sum_open_interest` (mixes all participants, already tested as a slow
regime filter in EXP-2026-09-01-OITREND-001, REJECTED) and distinct from the
CFTC COT "Leveraged Funds" data (weekly, CME-regulated, BTC/ETH-only,
already tested as a contrarian signal in EXP-2026-09-01-CFTCCOT-001,
REJECTED). This field has never been used as a signal in any prior study in
this repo. Mechanism tested here is FOLLOW (not contrarian): sustained
top-trader net-long positioning (fast 10d SMA of the ratio > slow 30d SMA)
should reflect informed accumulation and precede stronger price action.

## Design (frozen before results)

- Regime: `regime_on = SMA10(ratio) > SMA30(ratio)`, shift(1) applied so
  today's regime flag is only usable starting tomorrow (no lookahead).
- Execution: long the single asset at next daily open following a flip-on,
  exit at next daily open following flip-off. Non-overlapping blocks.
- Costs: 30bps round-trip (repo standard).
- Universe: BTC/ETH/SOL/XRP, restricted to each asset's real Binance
  futures metrics-archive coverage (BTC from 2020-09-01, ETH/SOL/XRP from
  2021-12-01). Missing archive days ffilled up to 3 days (matches observed
  real gap structure — 3-4 gaps per asset over the full history — never
  fabricated).
- Baselines: buy-and-hold, daily DCA, BTC-price-momentum regime control
  (same control used in the stablecoin-supply-trend and OI-trend studies),
  seeded random-regime control (matched block-length distribution/on-frac).

## Result

| Asset | Blocks | Primary final | B&H final | DCA final | Momentum ctrl | Random ctrl | Top-block % PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| BTC | 41 | 1.12x | 5.61x | 1.73x | 11.34x | 2.70x | -821% | REJECTED |
| ETH | 30 | 0.82x | 0.42x | 0.89x | 2.60x | 1.71x | +188% | REJECTED |
| SOL | 36 | 0.55x | 0.37x | 1.50x | 1.27x | 0.34x | -181% | REJECTED |
| XRP | 34 | 3.68x | 1.11x | 1.62x | 1.97x | 0.98x | +121% | REJECTED |

## Decisive blockers

1. **0/4 assets clear the concentration cap** — every asset's top block is
   over ±100% of total strategy PnL (some negative-PnL-share, indicating
   the signal actively works against itself in the largest block).
2. **BTC loses outright to every benchmark including its own random-timing
   control** (1.12x vs random 2.70x, BH 5.61x, momentum control 11.34x) —
   the deepest-history asset shows no genuine signal.
3. **3/4 assets lose to the naive BTC-momentum regime control** (BTC, ETH,
   SOL) — top-trader positioning trend adds no value over simple price
   momentum, the same failure mode as the OI-trend and stablecoin-supply-
   trend studies.
4. **0/4 assets survive doubled costs.**
5. XRP is the only asset that clears most gates on the surface (beats BH/
   DCA/momentum/random, survives doubled cost) but fails concentration
   (121% — apparent edge is one block) and best-block exclusion.

## Honest conclusion

**REJECTED, decisive.** Treating Binance top-trader positioning as a slow
structural regime signal shows the identical failure pattern already
established for aggregate OI-trend and stablecoin-supply-trend in this
program: concentration-artifact-driven apparent edges that vanish once the
single best block is excluded, and no incremental value over trivial price
momentum. This closes out a third "slow structural positioning/leverage
signal" family (aggregate OI, stablecoin supply, now top-trader ratio) with
the same result — do not retest this construction on Binance positioning
data without a fundamentally different mechanism (e.g. cross-sectional
top-trader-ratio divergence across assets, or a fast discrete-event
version rather than a slow SMA-crossover regime).

## Files

- `results/toptrader_positioning_trend/runs/run-20260902T013540Z/REPORT.md`
- `results/toptrader_positioning_trend/runs/run-20260902T013540Z/{BTC,ETH,SOL,XRP}_trades.csv`
- `results/toptrader_positioning_trend/runs/run-20260902T013540Z/{BTC,ETH,SOL,XRP}_gates.json`
- `scripts/toptrader_positioning_trend_validation.py`
