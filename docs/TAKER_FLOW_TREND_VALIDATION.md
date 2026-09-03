# Taker Buy-Volume-Ratio Trend Regime Filter Validation

Run: `results/taker_flow_trend/runs/run-20260903T225839Z/`

## Hypothesis (preregistered)

Binance's public spot klines endpoint discloses, per hourly bar, the fraction
of base-asset volume initiated by market-buy (taker-buy) orders vs total
volume in that bar (`taker_buy_base_asset_volume` / `volume`). A sustained
excess of taker buying over taker selling reflects persistent unlevered spot
demand -- distinct from open interest (levered positioning, already 4x
REJECTED in this repo) and funding (derivatives crowding, already multiply
REJECTED). Genuinely new real data source for this repo: no prior study used
Binance's aggressor-side trade classification.

Slow structural construction (per the skill's guidance to bias toward
slow-moving signals over fast oscillators): 3-day SMA of daily buy-ratio vs
14-day SMA, long the asset only while fast > slow (persistent buy-side
dominance), cash otherwise.

## Design

- Data: real Binance spot hourly klines including
  `taker_buy_base_asset_volume` (`data/taker_flow/{ASSET}_taker_flow_1h.csv.gz`,
  newly fetched this run via the public `/api/v3/klines` endpoint), BTC/ETH/
  SOL/XRP, full available history matching each asset's existing OHLCV
  coverage.
- Signal: daily volume-weighted taker-buy ratio, 3d SMA vs 14d SMA crossover,
  regime decided using data through day t, executed at day (t+1) 00:00 UTC
  open (one-day publication-equivalent lag, no lookahead).
- Costs: repo-standard 30bps round trip.
- Benchmarks: buy-and-hold, naive BTC-momentum regime control (long only
  while trailing-30d BTC return > 0), seeded random-regime control (same
  block count/on-time fraction, randomly placed).
- Falsification: primary must beat B&H, momentum control, AND random control
  on a majority (>=3/4) of assets; survive doubled cost; clear the 20%
  single-block concentration cap; not lose to B&H in the test partition.

## Result

| Asset | Blocks | Primary final | B&H final | Momentum control | Random control | Doubled cost | Excl-best-block | Top-block % PnL | Beats B&H |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| BTC | 392 | 1.94x | 4.73x | 13.70x | 0.82x | 0.60x | 1.30x | 32.3% | No |
| ETH | 378 | 0.73x | 1.40x | 16.91x | 0.05x | 0.24x | 0.41x | 61.3% | No |
| SOL | 262 | 2.66x | 22.21x | 81.66x | 2.74x | 1.22x | 1.45x | 27.8% | No |
| XRP | 368 | 1.74x | 1.62x | 5.64x | 1.96x | 0.58x | 0.76x | 51.0% | Yes |

**Gate tally: Beats B&H 1/4, beats momentum control 0/4, beats random control
2/4, survives doubled cost 0/4, concentration OK 0/4, excludes-best-block OK
0/4, test-partition pass 1/4.**

## Honest conclusion

**REJECTED, decisively.** The taker buy-ratio trend regime filter loses
outright to buy-and-hold on 3/4 assets, loses to a trivial BTC-price-momentum
regime control on all 4/4 assets (often by a wide margin -- e.g. SOL 2.66x
vs momentum's 81.66x), and fails the 20% concentration cap on all 4/4 assets
(27.8%-61.3% of total strategy PnL concentrated in a single regime block).
Zero assets survive doubled costs. XRP's lone B&H win is not robust: it
fails the concentration cap (51.0%), fails doubled cost, and fails
best-block exclusion.

## Decisive blockers

1. **Loses to the trivial momentum control on every asset**, undermining the
   core claim that spot taker-flow aggregation contains information beyond
   simple price trend.
2. **Concentration cap violated on all 4 assets** -- the now-familiar
   failure signature in this program (SMA200, DVOL, stablecoin-trend,
   OI-trend, top-trader-trend, retail-ratio, hash-ribbons all showed the
   same pattern): apparent edge is driven by a small number of large regime
   blocks, not a repeatable signal.
3. **Doubled costs are catastrophic on every asset** (0.24x-1.22x), and the
   413 (SOL) to 392 (BTC) regime-flip blocks per asset over the sample
   generate real turnover cost drag even at the base 30bps rate.

## Follow-up question

Real spot taker-buy-flow data is now cached
(`data/taker_flow/{BTC,ETH,SOL,XRP}_taker_flow_1h.csv.gz`) for any future
microstructure follow-up (e.g. as a fast confirmation filter on an existing
breakout system rather than a standalone slow regime signal). Do not retest
this exact 3d/14d SMA crossover on price-trend-following construction --
this is now the twelfth "slow structural signal loses to trivial momentum
and fails concentration" study in this program's positioning/flow-signal
family (after SMA200, DVOL, FGI, stablecoin-trend, OI-trend x2, top-trader-
trend, retail-ratio, hash-ribbons, orderbook-imbalance, NVT). Items 1-3 in
`docs/next_hypotheses.md` remain the highest-priority untested single-asset/
single-mechanism ideas.

## Files

- `results/taker_flow_trend/runs/run-20260903T225839Z/strategy_summary.csv`
- `results/taker_flow_trend/runs/run-20260903T225839Z/partition_summary.csv`
- `results/taker_flow_trend/runs/run-20260903T225839Z/{BTC,ETH,SOL,XRP}_trades.csv`
- `data/taker_flow/{BTC,ETH,SOL,XRP}_taker_flow_1h.csv.gz` (real Binance taker-flow cache)
- `scripts/fetch_taker_flow.py`
- `scripts/taker_flow_trend_validation.py`
