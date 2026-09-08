# GLD Trend Stress Regime Validation

- **Experiment ID:** EXP-2026-09-08-GLDTRENDSTRESS-001
- **Verdict:** REJECTED
- **Primary rule:** Use real Yahoo Finance GLD daily adjusted close as an external safe-haven trend/stress filter: hold BTC/ETH/SOL/XRP long only when GLD is **not** above its prior-only 200-trading-day SMA with positive prior-only 60-trading-day return. Crypto action is lagged one daily bar.
- **Why new:** This tests traded gold-ETF price trend/stress itself, distinct from the already-rejected gold-implied-volatility (`GVZCLS`) overlay and other macro equity/credit/rate/liquidity/FX/oil/copper filters.
- **Real data:** Yahoo Finance GLD daily adjusted close cached at `data/macro_gld_trend_stress/gld_1d.csv.gz` (2005-09-06 to 2026-07-27); cached Binance spot daily OHLCV; no synthetic/proxy inputs.

## Results

| Asset | Risk-on days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1d action lag | 2024+ final vs B&H | Sharpe | MaxDD | Top block PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| BTC | 1234 (39.4%) | 41 | $17,309.21 | $46,344.78 | $39,941.66 | $84,689.49 | $20,949.50 | $15,305.90 | $11,515.32 | $9,502.35 vs $15,032.99 (12 trades) | 0.36 | -67.4% | 158.4% | Rejected |
| ETH | 1234 (39.4%) | 41 | $15,931.53 | $25,741.27 | $34,753.86 | $127,304.60 | $7,295.29 | $14,087.66 | $9,796.62 | $10,037.73 vs $8,268.92 (12 trades) | 0.37 | -89.8% | 230.2% | Rejected |
| SOL | 881 (40.5%) | 32 | $688,339.07 | $259,570.99 | $40,615.95 | $904,985.48 | $73,324.98 | $625,330.96 | $624,349.83 | $13,541.00 vs $7,272.68 (12 trades) | 1.28 | -88.2% | 257.1% | Rejected |
| XRP | 1223 (40.7%) | 40 | $75,370.87 | $21,258.13 | $22,385.07 | $37,077.30 | $4,867.43 | $66,847.92 | $36,514.92 | $10,557.06 vs $17,268.99 (12 trades) | 0.58 | -70.9% | 75.9% | Rejected |

## Decisive checks

- Benchmark gate failed: 2/4 beat buy-and-hold, 2/4 beat DCA, 1/4 beat the BTC-momentum regime control.
- 2024+ holdout gate: 2/4 beat their own buy-and-hold benchmark.
- Concentration gate failed: 0/4 assets cleared the 20% top-PnL-block cap.
- GLD uptrend is real external safe-haven market data, but it does not add deployable value beyond crypto's own benchmarks under this standalone risk-off rule.

## Conclusion

- GLD trend stress does not produce a robust standalone crypto risk-off filter under this preregistered construction.
- Do not retest this same GLD 200d-SMA / 60d-return risk-off filter without a fundamentally different confirmation or sizing mechanism.
