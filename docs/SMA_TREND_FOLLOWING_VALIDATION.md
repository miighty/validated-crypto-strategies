# SMA(200) Trend-Following Validation

**Experiment ID:** EXP-2026-08-30-SMA-TREND-001

Run artifact: `results/sma_trend_following/runs/run-20260830T083930Z/`

## Hypothesis

Long only BTC/ETH/SOL/XRP while price is above its own trailing 200-day SMA,
flat (cash) otherwise, should beat continuous buy-and-hold after realistic
round-trip costs by avoiding the worst of prolonged bear-market drawdowns.
Real Binance spot 1d OHLCV only (`data/raw/*_1d.csv.gz`), no proxy/synthetic
data. Signal decided at close, executed at next day's open (no lookahead).
30bps round-trip cost (repo standard).

## Naive first-pass result

| Asset | Trend final ($1 start) | B&H final | Trend beats B&H | Doubled-cost survives | Sharpe |
|---|---:|---:|---:|---:|---:|
| BTC | 9.68x | 8.54x | Yes | Yes | 0.87 |
| ETH | 16.24x | 4.04x | Yes | Yes | 0.89 |
| SOL | 25.84x | 5.46x | Yes | Yes | 1.15 |
| XRP | 0.76x | 2.21x | No | No | 0.32 |

3/4 assets beat buy-and-hold, doubled-cost survives, only 1 test-partition
loss — on these first-pass numbers alone this would clear the preregistered
CANDIDATE bar.

## Decisive hostile check: best-trade exclusion

Per this repo's standard concentration audit, PnL was recomputed excluding
each asset's single best trade:

| Asset | Compounded return (all trades) | Compounded return (best trade excluded) | B&H | Excl-best beats B&H? |
|---|---:|---:|---:|---:|
| BTC | 9.68x | 2.32x | 8.54x | **No** |
| ETH | 16.24x | 1.65x | 4.04x | **No** |
| SOL | 25.84x | 2.60x | 5.46x | **No** |
| XRP | 0.76x | 0.23x | 2.21x | **No** |

On every single asset, the entire apparent edge over buy-and-hold evaporates
once the one best trade is removed — in all four cases the best trade is the
Oct 2023 -> mid-2024 SMA-reclaim that rode the last major bull leg. SOL's
best trade alone was **130% of the strategy's total net PnL** (a single
trade PnL larger than the strategy's entire net profit), a decisive
concentration red flag independent of Sharpe.

## Honest conclusion

**REJECTED.** The naive "beats buy-and-hold on 3/4 assets" result is a
concentration artifact of catching one large trend move per asset, not a
genuine trend-following edge. This matches the skill's documented pattern:
flag any strategy where a single trade dominates realized PnL, regardless of
how good the naive metrics look. This differs from the cross-asset SMA200
near-miss finding on SPY/QQQ/GLD (Sharpe 0.22-0.31, concentration checked and
passed) — crypto's much larger, fewer, more concentrated trend moves make a
single-signal SMA filter structurally more concentration-prone here than on
equities/commodities.

## Files

- `results/sma_trend_following/runs/run-20260830T083930Z/strategy_summary.csv`
- `results/sma_trend_following/runs/run-20260830T083930Z/partition_summary.csv`
- `results/sma_trend_following/runs/run-20260830T083930Z/{BTC,ETH,SOL,XRP}_trend_trades.csv`
