# Coinbase-vs-Binance Price Premium Contrarian Validation

Run artifact: `results/coinbase_premium_contrarian/runs/run-20260903T070043Z/REPORT.md`

## Hypothesis

The real, widely-cited "Coinbase Premium Index" (Coinbase spot price vs Binance
spot price) reflects US institutional (Coinbase) vs global/offshore/retail
(Binance) demand imbalance. This tests the CONTRARIAN construction: an
unusually large *negative* premium (Coinbase trading at a rare discount to
Binance, z <= -2.0 vs its own trailing 30-day history) signals a temporary
US-led panic/flush that should mean-revert — buy the discount, hold 24h.

Genuinely new for this repo: first use of Coinbase Exchange data and the first
cross-exchange *spot price* premium signal (distinct from the already-REJECTED
perp-vs-perp funding divergence study, `FUNDING_CROSSEXCHANGE_DIVERGENCE_VALIDATION.md`,
and the Bybit/OKX Amihud cross-checks which used cross-exchange data for
robustness confirmation, not as a standalone signal).

## Data

- Real Coinbase Exchange public hourly OHLCV, `GET /products/{id}/candles`,
  newly fetched this run (`data/coinbase_premium/{BTC,ETH}_coinbase_1h.csv.gz`,
  75,079 / 75,096 rows, full 2018-01-01 → 2026-07-27 coverage).
- Real Binance spot hourly OHLCV (`data/raw/{BTC,ETH}_1h.csv.gz`, already
  cached) for execution.
- BTC/ETH only — Coinbase does not have comparable continuous SOL/XRP spot
  history (XRP delisted during the SEC lawsuit; SOL/USD history is materially
  shorter). No proxy fabricated.

## Result table

| Asset | Trades | Primary final ($1 start) | B&H final | DCA final | Random control | Verdict |
|---|---:|---:|---:|---:|---:|---|
| BTC | 492 | 0.0141 | 4.6345 | 3.9930 | 0.9321 | **Rejected** |
| ETH | 495 | 0.0107 | 2.5741 | 3.4749 | 1.0171 | **Rejected** |

## Honest conclusion

> **Rejected, decisively.** Both assets lost ~98-99% of capital outright over
> 492-495 non-overlapping 24h trades. Mean trade return was negative in every
> partition for both assets (-0.65% to -0.96% per trade). The threshold
> (z <= -2.0) fires far too often (~490 times in 8 years, roughly once every
> 6 days) to represent a "rare panic" — it is picking up ordinary short-term
> volatility, not a genuine dislocation. Buying immediately on the discount
> reading with no reclaim confirmation buys into ongoing declines, the same
> failure mode as this program's other "buy the panic" rejections (DVOL
> fear-spike, FGI extreme-fear, volume-flush rebound). The strategy also
> underperforms its own random-timing control on both assets, meaning the
> z-score threshold carries *negative* timing value versus chance.

## Decisive checks

- **Doubled-cost check:** BTC falls further to 0.0032; ETH to 0.0024 — cost is
  not the primary driver of the loss, the signal itself is actively harmful.
- **Best-trade exclusion:** BTC 0.0209, ETH 0.0179 — still far below cash/B&H;
  concentration is not masking a real edge (BTC top-trade share 10.5%, ETH
  20.7%, both within/near the 20% cap, confirming the loss is broad-based
  across trades, not one outlier).
- **Holdout:** both assets had real 2024+ trades (143/146), consistent
  negative mean return in every partition — no regime where this worked.

## Files

- `results/coinbase_premium_contrarian/runs/run-20260903T070043Z/summary.csv`
- `results/coinbase_premium_contrarian/runs/run-20260903T070043Z/{BTC,ETH}_trades.csv`
- `results/coinbase_premium_contrarian/runs/run-20260903T070043Z/{BTC,ETH}_gates.json`
- `data/coinbase_premium/{BTC,ETH}_coinbase_1h.csv.gz` (newly fetched, cached for any future Coinbase-premium follow-up)
