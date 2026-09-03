# Coinbase-vs-Binance Price Premium TREND-FOLLOWING Regime Validation

Run artifact: `results/coinbase_premium_trend_regime/runs/run-20260903T194023Z/REPORT.md`

## Hypothesis

The already-REJECTED Coinbase premium CONTRARIAN study
(`docs/COINBASE_PREMIUM_CONTRARIAN_VALIDATION.md`) explicitly named the mirror
TREND-FOLLOWING construction ("persistent premium predicts continuation, not
reversion") as an untested follow-up. This tests it: a sustained (24h
trailing mean, prior-only) POSITIVE Coinbase-vs-Binance spot premium signals
persistent US institutional buying pressure and should precede continued
upside — long spot while the regime is "on", cash otherwise. Genuinely new
construction (slow structural regime filter, not the contrarian study's
single-hour z-score event trigger) reusing already-cached real Coinbase
Exchange data.

## Data

- Real Coinbase Exchange hourly OHLCV (already cached, no new fetch).
- Real Binance spot hourly OHLCV (already cached) for execution.
- BTC/ETH only (same data-availability limitation as the parent study).

## Result table

| Asset | Blocks | Primary final ($1) | B&H | DCA | Momentum control | Random control | Top-block % PnL | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| BTC | 297 | 4.16 | 4.63 | 3.99 | 4.41 | 1.03 | 38.8% | **Rejected** |
| ETH | 357 | 15.35 | 2.57 | 3.47 | 19.73 | 1.43 | 47.8% | **Rejected** |

## Honest conclusion

> **Rejected, decisively — 0/2 assets clear the concentration cap or beat the
> naive momentum control.** BTC's regime beats DCA and its own random-regime
> control but loses outright to buy-and-hold and to a trivial trailing-30d
> price-momentum regime filter; it also fails the best-block-exclusion check
> (drops below buy-and-hold once the single largest block is removed) and
> the 20% concentration cap (38.8% of PnL in one block). ETH beats
> buy-and-hold/DCA/random control and survives best-block exclusion, but
> still loses to the simple price-momentum control (19.73x vs 15.35x) and
> fails the concentration cap (47.8% of PnL in one block). In both cases the
> "genuinely new" cross-exchange premium regime signal adds no incremental
> value over just trading on the asset's own trailing price momentum — the
> premium regime is highly correlated with (and worse than) plain momentum,
> not an independent source of edge. Consistent with this program's
> established slow-structural-regime failure pattern (OI-trend,
> stablecoin-supply-trend, top-trader-trend all showed the identical
> "loses to naive momentum control + concentration cap violated" signature).

## Decisive checks

- **Doubled-cost check:** both assets remain net positive but this is moot —
  they already fail on the primary economic/concentration gates.
- **Momentum-control comparison:** BTC 4.16x vs 4.41x momentum (loses); ETH
  15.35x vs 19.73x momentum (loses) — the premium regime is not adding
  information beyond price momentum.
- **Concentration:** both assets fail the 20% single-block PnL cap (38.8%,
  47.8%).

## Files

- `results/coinbase_premium_trend_regime/runs/run-20260903T194023Z/summary.csv`
- `results/coinbase_premium_trend_regime/runs/run-20260903T194023Z/{BTC,ETH}_trades.csv`
- `results/coinbase_premium_trend_regime/runs/run-20260903T194023Z/{BTC,ETH}_gates.json`
- `scripts/coinbase_premium_trend_regime_validation.py`
