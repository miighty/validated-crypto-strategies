# Order-Book Depth Imbalance (Contrarian-Liquidity) Validation

Run artifact: `results/orderbook_imbalance/runs/run-20260902T150811Z/REPORT.md`

## Hypothesis

Genuinely new data source for this repo: real Binance USD-M futures order-book
depth archive (`data.binance.vision/.../bookDepth/`), never used in any prior
study — every prior positioning/crowding study used funding, open interest, CME
COT, or sentiment indices, never the raw limit order book. Fetched and
aggregated (mean notional depth within 1-2% of mid, both sides) to one row/day,
2023-01-01 through 2026-09-01, all 4 assets (`scripts/fetch_orderbook_depth.py`).

Mechanism: a book unusually bid-heavy vs. its own trailing 90-day history
(z >= +1.5) signals liquidity providers willing to absorb selling pressure near
price — long spot, hold 7 days, non-overlapping.

## Result table

| Asset | Trades | Primary final | Buy-and-hold | DCA | Random control | Top trade % PnL | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| BTC | 51 | 0.94x | 3.84x | 1.24x | 1.10x | 271.6% | REJECTED |
| ETH | 47 | 2.36x | 1.58x | 0.81x | 1.34x | 23.9% | REJECTED |
| SOL | 50 | 0.67x | 7.42x | 1.28x | 0.55x | -67.8% | REJECTED |
| XRP | 46 | 0.47x | 3.14x | 1.35x | 0.66x | -61.8% | REJECTED |

## Honest conclusion

**REJECTED, decisively, 0/4 assets.** BTC/SOL/XRP lose outright to buy-and-hold
and DCA (SOL/XRP also lose absolute capital, finishing below the $1 start).
ETH is the lone asset that beats every benchmark including doubled cost, but
its edge fails the 20% concentration cap (23.9% of total PnL in a single
trade) — same failure signature as nine prior positioning-style studies in
this program. Real order-book depth data adds no incremental value as a
contrarian-liquidity timing signal at this threshold/window/hold on any of
the 4 assets tested.

## Files

- `results/orderbook_imbalance/runs/run-20260902T150811Z/REPORT.md`
- `results/orderbook_imbalance/runs/run-20260902T150811Z/summary.csv`
- `results/orderbook_imbalance/runs/run-20260902T150811Z/{BTC,ETH,SOL,XRP}_trades.csv`
- `results/orderbook_imbalance/runs/run-20260902T150811Z/{BTC,ETH,SOL,XRP}_gates.json`
- `data/orderbook_depth/{BTC,ETH,SOL,XRP}_depth_imbalance_1d.csv.gz` (newly cached real data)
