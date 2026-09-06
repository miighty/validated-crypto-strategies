# BAA Credit-Spread Risk-Off Overlay Validation

- **Experiment ID:** EXP-2026-09-06-BAACREDITRISKOFF-001
- **Verdict:** REJECTED
- **Primary rule:** If real FRED Moody's Seasoned BAA Corporate Bond Yield minus real FRED 10-Year Treasury Constant Maturity (`DBAA - DGS10`) z-score >= +2.0 vs a prior-only 252-trading-day baseline, exit BTC/ETH/SOL/XRP at the next daily open; stay cash until z < +1.0, then re-enter at the next daily open.
- **Why new:** First credit-spread macro signal in this repo; distinct from VIX volatility stress and DXY dollar trend.
- **Real data:** FRED DBAA and DGS10 cached at `data/macro_credit/baa_treasury_spread_1d.csv.gz` (1987-01-06 to 2026-07-27); cached Binance spot daily OHLCV; no synthetic/proxy inputs.

## Results

| Asset | Risk-off days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1d action lag | 2024+ final vs B&H | Sharpe | MaxDD | Top block PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| BTC | 411 (13.1%) | 7 | $45,847.17 | $46,344.78 | $39,941.66 | $84,689.49 | $39,692.76 | $44,894.42 | $38,398.15 | $12,188.67 vs $15,032.99 (2 trades) | 0.60 | -79.6% | 150.7% | Rejected |
| ETH | 411 (13.1%) | 7 | $16,490.39 | $25,741.27 | $34,753.86 | $127,304.60 | $20,528.63 | $16,147.70 | $16,490.25 | $6,223.81 vs $8,268.92 (2 trades) | 0.45 | -87.8% | 649.1% | Rejected |
| SOL | 165 (7.6%) | 5 | $307,123.32 | $259,570.99 | $40,615.95 | $904,985.48 | $309,792.93 | $302,550.83 | $305,450.90 | $6,258.35 vs $7,272.68 (2 trades) | 1.05 | -94.9% | 144.3% | Rejected |
| XRP | 411 (13.7%) | 7 | $31,207.09 | $21,258.13 | $22,385.07 | $37,077.30 | $15,515.79 | $30,558.57 | $26,843.60 | $17,186.84 vs $17,268.99 (2 trades) | 0.53 | -84.5% | 241.3% | Rejected |

## Decisive checks

- Benchmark gate failed: 2/4 beat buy-and-hold, 3/4 beat DCA, 0/4 beat the BTC-momentum regime control.
- Concentration gate failed: 0/4 assets cleared the 20% top-PnL-block cap.
- Test partition gate failed: 0/4 assets beat their own 2024+ buy-and-hold benchmark.
- Credit-spread stress is a stale/lagging de-risking overlay for crypto in this construction: it removes exposure during broad stress but misses too much of the subsequent recovery.

## Conclusion

- BAA-minus-Treasury credit-spread stress does not add deployable standalone timing value against simple crypto baselines.
- This rejects the simplest external-credit risk-off overlay; do not retest the same z>=2 / z<1 hysteresis construction without a fundamentally different sizing or confirmation rule.
