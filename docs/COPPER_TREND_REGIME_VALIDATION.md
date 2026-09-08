# Copper Trend Regime Validation

- **Experiment ID:** EXP-2026-09-08-COPPERTREND-001
- **Verdict:** REJECTED
- **Primary rule:** Use real FRED PCOPPUSDM monthly copper prices as an external industrial-demand / cyclical-growth risk-on filter: long BTC/ETH/SOL/XRP only when copper > prior-only 12-month SMA and prior-only 3-month change > 0; otherwise cash. Crypto action is lagged one monthly print.
- **Why new:** This is the first industrial-metals macro signal in the repo, distinct from already-tested equity-index trend, implied volatility, rates, credit, liquidity, oil, DXY, consumer-sentiment, and crypto-native flow/positioning studies.
- **Real data:** FRED PCOPPUSDM cached at `data/macro_copper_trend/pcoppusdm_1mo.csv.gz` (1993-01-01 to 2026-07-01); cached Binance spot daily OHLCV; no synthetic/proxy inputs.

## Results

| Asset | Risk-on days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1 print lag | 2024+ final vs B&H | Sharpe | MaxDD | Top block PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| BTC | 1544 (49.3%) | 12 | $27,155.93 | $46,344.78 | $39,941.66 | $84,689.49 | $6,746.91 | $26,195.69 | $18,536.29 | $6,913.41 vs $15,032.99 (5 trades) | 0.49 | -76.8% | 274.6% | Rejected |
| ETH | 1544 (49.3%) | 12 | $62,852.78 | $25,741.27 | $34,753.86 | $127,304.60 | $2,667.64 | $60,630.32 | $32,348.27 | $5,757.25 vs $8,268.92 (5 trades) | 0.65 | -86.3% | 417.7% | Rejected |
| SOL | 1293 (59.4%) | 9 | $25,079.36 | $259,570.99 | $40,615.95 | $904,985.48 | $29,189.11 | $24,411.27 | $76,905.02 | $3,300.03 vs $7,272.68 (5 trades) | 0.60 | -96.5% | 3213.6% | Rejected |
| XRP | 1424 (47.4%) | 11 | $19,557.07 | $21,258.13 | $22,385.07 | $37,077.30 | $17,595.58 | $18,922.22 | $25,120.93 | $6,235.99 vs $17,268.99 (5 trades) | 0.48 | -85.2% | 467.2% | Rejected |

## Decisive checks

- Benchmark gate failed: 1/4 beat buy-and-hold, 1/4 beat DCA, 0/4 beat the BTC-momentum regime control.
- 2024+ holdout gate: 0/4 beat their own buy-and-hold benchmark.
- Concentration gate failed: 0/4 assets cleared the 20% top-PnL-block cap.
- Monthly copper trend is a real external cyclical-growth input, but it is too slow and sparse to add deployable timing value under this standalone construction.

## Conclusion

- Copper industrial-demand trend does not produce a robust standalone crypto risk-on filter.
- Do not retest this same PCOPPUSDM 12-month-SMA / 3-month-change rule without a fundamentally different confirmation or sizing mechanism.
