# S&P 500 Trend Regime Validation

- **Experiment ID:** EXP-2026-09-08-SP500TREND-001
- **Verdict:** REJECTED
- **Primary rule:** Use real FRED SP500 daily closes as a broad-equity risk-appetite filter: hold BTC/ETH/SOL/XRP long only when SP500 close > prior-only 200-trading-day SMA; otherwise cash. Crypto action is lagged one daily bar.
- **Why new:** This tests external equity-price trend specifically, distinct from already-rejected equity implied-volatility overlays (VIX/VXN), credit/rate/liquidity macro overlays, and crypto-derived momentum/flow filters.
- **Real data:** FRED SP500 cached at `data/macro_sp500_trend/sp500_1d.csv.gz` (2017-06-22 to 2026-07-27); cached Binance spot daily OHLCV; no synthetic/proxy inputs.

## Results

| Asset | Risk-on days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1d action lag | 2024+ final vs B&H | Sharpe | MaxDD | Top block PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| BTC | 2496 (79.7%) | 29 | $59,662.08 | $46,344.78 | $39,941.66 | $84,689.49 | $10,936.01 | $54,690.83 | $44,423.17 | $11,133.31 vs $15,032.99 (4 trades) | 0.66 | -67.4% | 110.8% | Rejected |
| ETH | 2496 (79.7%) | 29 | $33,626.35 | $25,741.27 | $34,753.86 | $127,304.60 | $82,341.74 | $30,824.49 | $20,303.10 | $5,772.93 vs $8,268.92 (4 trades) | 0.55 | -88.1% | 216.5% | Rejected |
| SOL | 1753 (80.5%) | 16 | $379,835.63 | $259,570.99 | $40,615.95 | $904,985.48 | $60,063.82 | $362,034.08 | $343,379.19 | $5,134.01 vs $7,272.68 (4 trades) | 1.07 | -84.9% | 152.9% | Rejected |
| XRP | 2374 (78.9%) | 28 | $37,193.84 | $21,258.13 | $22,385.07 | $37,077.30 | $1,770.57 | $34,197.16 | $17,600.24 | $14,057.78 vs $17,268.99 (4 trades) | 0.54 | -74.3% | 222.9% | Rejected |

## Decisive checks

- Benchmark gate failed: 4/4 beat buy-and-hold, 3/4 beat DCA, 1/4 beat the BTC-momentum regime control.
- 2024+ holdout gate: 0/4 beat their own buy-and-hold benchmark.
- Concentration gate failed: 0/4 assets cleared the 20% top-PnL-block cap.
- The SP500 200d trend state is a slow external regime variable, but it does not add deployable value beyond crypto's own benchmarks under this rule.

## Conclusion

- S&P 500 price-trend risk appetite does not produce a robust standalone crypto regime filter under this preregistered construction.
- Do not retest this same SP500 200d-SMA risk-on filter without a fundamentally different confirmation or sizing mechanism.
