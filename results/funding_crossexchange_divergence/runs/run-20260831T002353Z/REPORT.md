# Cross-Exchange (Binance vs Hyperliquid) Funding Divergence Validation

## Primary rule
> Cross-exchange funding basis: at each real Binance 8h settlement, compute the matching real Hyperliquid 8h-compounded funding rate for the same asset. If |Binance_8h - Hyperliquid_8h| >= 5bps, enter a perp-vs-perp basis trade: long the perp on the exchange with the LOWER funding rate, short the perp on the exchange with the HIGHER funding rate, equal notional (net price-neutral by construction). Hold exactly 1 settlement (8h), collect the realized funding differential, exit, and reassess at the next settlement. No spot leg is used (distinct from the already-rejected single-exchange delta-neutral carry study).

## Honesty disclosures
- Hyperliquid public funding history only reaches back to 2023-05-12 (BTC/ETH/SOL) / 2023-06-18 (XRP); the comparison window is the intersection of both exchanges' real history, reported per asset below -- this is a much shorter sample than the repo's other funding studies.
- No cross-exchange collateral-transfer friction or exchange-specific liquidation risk modeled beyond the shared round-trip cost model.
- Real data only: Binance real 8h funding (already cached) + Hyperliquid real hourly funding (fetched this run via the public `fundingHistory` endpoint, compounded to 8h windows aligned to Binance settlements). No synthetic/proxy funding data.

## Per-asset results

### BTC
- Overlap window: **2023-06-08 08:00:00+00:00** -> **2026-07-27 16:00:00.001000+00:00** (3297 matched settlements)
- Mean |divergence|: **1.00 bps**
- Trades: **71**
- Final capital: **$6865.66** (-31.34%), Sharpe **-41.80**, Sortino **-4.73**, max drawdown **-31.34%**
- Random-timing control final: **$6525.17**
- Doubled-cost final: **$4475.45**
- Best-trade-exclusion final: **$8504.59** (best trade = 0.2% of total PnL)
- Walk-forward: first half **-29.87%** (67 trades), second half **-2.09%** (4 trades)
- Verdict: **REJECTED**

### ETH
- Overlap window: **2023-06-08 08:00:00+00:00** -> **2026-07-27 16:00:00.001000+00:00** (3297 matched settlements)
- Mean |divergence|: **1.00 bps**
- Trades: **77**
- Final capital: **$6615.71** (-33.84%), Sharpe **-87.40**, Sortino **-4.95**, max drawdown **-33.84%**
- Random-timing control final: **$6275.65**
- Doubled-cost final: **$4159.35**
- Best-trade-exclusion final: **$8353.66** (best trade = 0.5% of total PnL)
- Walk-forward: first half **-31.67%** (71 trades), second half **-3.18%** (6 trades)
- Verdict: **REJECTED**

### SOL
- Overlap window: **2023-06-08 08:00:00+00:00** -> **2026-07-27 16:00:00.001000+00:00** (3297 matched settlements)
- Mean |divergence|: **1.39 bps**
- Trades: **174**
- Final capital: **$4005.27** (-59.95%), Sharpe **-64.80**, Sortino **-7.40**, max drawdown **-59.95%**
- Random-timing control final: **$3515.04**
- Doubled-cost final: **$1403.39**
- Best-trade-exclusion final: **$6761.98** (best trade = 0.1% of total PnL)
- Walk-forward: first half **-58.63%** (168 trades), second half **-3.19%** (6 trades)
- Verdict: **REJECTED**

### XRP
- Overlap window: **2023-06-18 08:00:00+00:00** -> **2026-07-27 16:00:00.001000+00:00** (3267 matched settlements)
- Mean |divergence|: **1.04 bps**
- Trades: **90**
- Final capital: **$6179.05** (-38.21%), Sharpe **-60.70**, Sortino **-5.36**, max drawdown **-38.21%**
- Random-timing control final: **$5816.88**
- Doubled-cost final: **$3592.05**
- Best-trade-exclusion final: **$8105.93** (best trade = 0.2% of total PnL)
- Walk-forward: first half **-32.42%** (73 trades), second half **-8.57%** (17 trades)
- Verdict: **REJECTED**

## Summary table
| asset | n_trades | final_capital | total_return_pct | sharpe | verdict |
| --- | --- | --- | --- | --- | --- |
| BTC | 71 | 6865.6638 | -31.3434 | -41.7974 | REJECTED |
| ETH | 77 | 6615.7098 | -33.8429 | -87.3950 | REJECTED |
| SOL | 174 | 4005.2696 | -59.9473 | -64.8025 | REJECTED |
| XRP | 90 | 6179.0513 | -38.2095 | -60.6988 | REJECTED |

## Sensitivity grid (final capital, $10,000 start)
| asset | divergence_threshold_bps | hold_prints | n_trades | final_capital | total_return_pct |
| --- | --- | --- | --- | --- | --- |
| BTC | 2.5000 | 1 | 300 | 1876.9154 | -81.2308 |
| BTC | 5.0000 | 1 | 71 | 6865.6638 | -31.3434 |
| BTC | 10.0000 | 1 | 5 | 9775.2124 | -2.2479 |
| BTC | 5.0000 | 3 | 45 | 8166.5516 | -18.3345 |
| BTC | 10.0000 | 3 | 3 | 9903.6375 | -0.9636 |
| ETH | 2.5000 | 1 | 339 | 1500.3389 | -84.9966 |
| ETH | 5.0000 | 1 | 77 | 6615.7098 | -33.8429 |
| ETH | 10.0000 | 1 | 2 | 9902.1222 | -0.9788 |
| ETH | 5.0000 | 3 | 50 | 7926.3986 | -20.7360 |
| ETH | 10.0000 | 3 | 2 | 9924.3569 | -0.7564 |
| SOL | 2.5000 | 1 | 488 | 678.5441 | -93.2146 |
| SOL | 5.0000 | 1 | 174 | 4005.2696 | -59.9473 |
| SOL | 10.0000 | 1 | 25 | 8879.7455 | -11.2025 |
| SOL | 5.0000 | 3 | 88 | 6872.4600 | -31.2754 |
| SOL | 10.0000 | 3 | 17 | 9460.4572 | -5.3954 |
| XRP | 2.5000 | 1 | 361 | 1330.9129 | -86.6909 |
| XRP | 5.0000 | 1 | 90 | 6179.0513 | -38.2095 |
| XRP | 10.0000 | 1 | 4 | 9818.7324 | -1.8127 |
| XRP | 5.0000 | 3 | 53 | 7844.1462 | -21.5585 |
| XRP | 10.0000 | 3 | 4 | 9861.5873 | -1.3841 |

## Overall verdict
0/4 assets fully cleared all gates (beat cash, beat random-timing control, survive doubled cost, survive best-trade exclusion, concentration < 100% of PnL, positive in both walk-forward halves, >= 20 trades).

**REJECTED** -- no asset cleared every gate.
