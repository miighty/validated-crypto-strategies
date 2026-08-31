# Stablecoin Supply Growth Trend (Fundamental Liquidity-Flow Regime Filter) Validation

Run artifact: `results/stablecoin_supply_trend/runs/run-20260831T225847Z/`

## Hypothesis

Real DefiLlama aggregate stablecoin supply (USDT+USDC+... total USD circulating,
daily, 2019-06-01 onward) growing (7d SMA > 30d SMA) signals accelerating fiat
inflow into crypto and should precede risk-on price action. A rule that goes
long BTC/ETH/SOL/XRP only while this regime is "on" (one-day publication lag,
non-overlapping blocks, 30bps round-trip costs) should beat continuous
buy-and-hold, a naive BTC-momentum regime control, and a seeded random-regime
control.

Genuinely new data source (DefiLlama stablecoin supply, first use in this
repo) and new mechanism (fundamental fiat-flow regime filter, distinct from
every prior calendar/factor/trend/vol/event-odds study).

## Result table

| Asset | Primary final | B&H final | Momentum control final | Random control final | Beats B&H | Beats momentum | Beats random | Doubled cost | Excl. best block |
|---|---:|---:|---:|---:|---|---|---|---|---|
| BTC | 5.60x | 7.46x | 12.58x | 5.62x | No | No | No | No | No |
| ETH | 8.40x | 7.16x | 52.40x | 10.14x | Yes | No | No | Yes | No |
| SOL | 56.70x | 22.50x | 81.66x | 0.52x | Yes | No | Yes | Yes | No |
| XRP | 3.82x | 2.49x | 12.97x | 0.43x | Yes | No | Yes | Yes | No |

- Regime "on" 74.7% of full sample (2,585 regime-days) -- 19 blocks per asset (BTC/ETH/XRP), 16 (SOL).
- Test-partition (2024-01-01 onward) beats B&H on all 4 assets, but this is the only gate that passes.

## Decisive blockers

1. **Momentum control dominates on every single asset** -- the naive
   "long only while trailing-30d BTC return > 0" filter beat the stablecoin
   regime filter by a wide margin on BTC (12.58x vs 5.60x), ETH (52.40x vs
   8.40x), SOL (81.66x vs 56.70x), and XRP (12.97x vs 3.82x). The
   fundamental-flow signal adds no value over a much simpler price-momentum
   regime filter.
2. **Best-block exclusion concentration artifact on all 4 assets** -- removing
   the single best on-regime block drops every asset's terminal value below
   1.0x (BTC 1.28x -> still positive but far below B&H 7.46x; ETH 0.64x; SOL
   1.87x; XRP 0.93x), consistent with this program's repeated finding that
   crypto's largest trend moves are too concentrated in a handful of blocks
   for a binary regime filter to pass the concentration audit.
3. **Development and validation partitions both lose to B&H on 3/4 assets**
   (only XRP's validation partition wins) -- the apparent test-partition win
   is not corroborated earlier in the sample.
4. Only 1 of 4 assets (BTC on dev/val split notwithstanding) beats B&H
   overall; 0/4 beat the momentum control; 0/4 survive best-block exclusion.

## Honest conclusion

**REJECTED.** Stablecoin supply growth, even as a slow-moving fundamental
regime filter (per the skill's guidance to prefer structural signals over
fast oscillators), carries no incremental value over a trivial BTC-momentum
regime filter, and the apparent edge over buy-and-hold on 3/4 assets is a
concentration artifact (fails once the single best regime block is excluded)
-- the same failure mode as SMA-200 and DVOL-fear-spike in this program.

## Files

- `results/stablecoin_supply_trend/runs/run-20260831T225847Z/strategy_summary.csv`
- `results/stablecoin_supply_trend/runs/run-20260831T225847Z/partition_summary.csv`
- `results/stablecoin_supply_trend/runs/run-20260831T225847Z/regime_signal.csv.gz`
- `results/stablecoin_supply_trend/runs/run-20260831T225847Z/{BTC,ETH,SOL,XRP}_trades.csv`
- `data/stablecoin_supply/total_stablecoin_supply_1d.csv.gz` (real DefiLlama data, newly fetched and cached this run)
