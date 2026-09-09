# LQD Investment-Grade Credit ETF Trend Regime Validation

- **Experiment ID:** EXP-2026-09-09-LQDTREND-001
- **Verdict:** REJECTED
- **Primary rule:** Use real Yahoo Finance LQD adjusted daily closes as an external investment-grade credit risk-appetite filter: hold BTC/ETH/SOL/XRP long only when LQD adjusted close > prior-only 200-trading-day SMA; otherwise cash. Crypto action is lagged one daily bar.
- **Why new:** This tests traded investment-grade corporate-bond ETF trend specifically, distinct from already-rejected high-yield credit ETF, credit-spread z-score, broad equity, rates, liquidity, FX, commodity, and crypto-native filters.
- **Real data:** Yahoo Finance LQD adjusted close cached at `data/macro_lqd_trend/lqd_1d.csv.gz` (2015-08-19 to 2026-07-27); cached Binance spot daily OHLCV; no synthetic/proxy inputs.

## Results

| Asset | Risk-on days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1d action lag | 2024+ final vs B&H | Sharpe | MaxDD | Top block PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| BTC | 2074 (66.3%) | 40 | $247,556.89 | $46,344.78 | $39,941.66 | $84,689.49 | $48,213.78 | $219,563.13 | $124,210.34 | $9,377.16 vs $15,032.99 (20 trades) | 1.02 | -65.3% | 157.2% | Rejected |
| ETH | 2074 (66.3%) | 40 | $211,568.38 | $25,741.27 | $34,753.86 | $127,304.60 | $3,509.39 | $187,644.20 | $88,223.88 | $5,215.90 vs $8,268.92 (20 trades) | 0.87 | -74.0% | 123.0% | Rejected |
| SOL | 1464 (67.2%) | 34 | $127,043.79 | $259,570.99 | $40,615.95 | $904,985.48 | $774,538.68 | $114,724.23 | $260,826.78 | $3,626.52 vs $7,272.68 (20 trades) | 0.88 | -88.4% | 388.8% | Rejected |
| XRP | 2039 (67.8%) | 39 | $32,674.51 | $21,258.13 | $22,385.07 | $37,077.30 | $3,745.80 | $29,066.75 | $18,013.98 | $10,233.34 vs $17,268.99 (20 trades) | 0.56 | -78.3% | 367.6% | Rejected |

## Decisive checks

- Benchmark gate failed: 3/4 beat buy-and-hold, 4/4 beat DCA, and 2/4 beat the BTC-momentum regime control.
- 2024+ holdout gate: 0/4 beat their own buy-and-hold benchmark.
- Concentration gate failed: 0/4 assets cleared the 20% top-PnL-block cap.
- The LQD 200d trend state is a slow external credit-risk-appetite variable, but it does not add deployable value beyond crypto's own benchmarks under this rule.

## Conclusion

- LQD investment-grade credit ETF trend risk appetite does not produce a robust standalone crypto regime filter under this preregistered construction.
- Do not retest this same LQD 200d-SMA risk-on filter without a fundamentally different confirmation or sizing mechanism.
