# Dow Jones Industrial Average Trend Regime Validation

- **Experiment ID:** EXP-2026-09-08-DJIATREND-001
- **Verdict:** REJECTED
- **Primary rule:** Use real FRED DJIA daily closes as a blue-chip-equity risk-appetite filter: hold BTC/ETH/SOL/XRP long only when DJIA close > prior-only 200-trading-day SMA; otherwise cash. Crypto action is lagged one daily bar.
- **Why new:** This tests Dow/old-economy blue-chip equity-price trend specifically, distinct from already-tested S&P 500 and Nasdaq Composite price-trend filters, equity implied-volatility overlays (VIX/VXN), credit/rate/liquidity macro overlays, and crypto-derived momentum/flow filters.
- **Real data:** FRED DJIA cached at `data/macro_djia_trend/djia_1d.csv.gz` (2017-06-22 to 2026-07-27); cached Binance spot daily OHLCV; no synthetic/proxy inputs.

## Results

| Asset | Risk-on days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1d action lag | 2024+ final vs B&H | Sharpe | MaxDD | Top block PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| BTC | 2470 (78.9%) | 36 | $35,129.94 | $46,344.78 | $39,941.66 | $84,689.49 | $34,295.76 | $31,533.59 | $34,264.52 | $11,400.55 vs $15,032.99 (10 trades) | 0.55 | -75.4% | 171.5% | Rejected |
| ETH | 2470 (78.9%) | 36 | $17,371.32 | $25,741.27 | $34,753.86 | $127,304.60 | $45,574.34 | $15,592.97 | $11,320.19 | $6,145.70 vs $8,268.92 (10 trades) | 0.45 | -91.2% | 845.7% | Rejected |
| SOL | 1751 (80.4%) | 23 | $199,421.90 | $259,570.99 | $40,615.95 | $904,985.48 | $1,485,538.27 | $186,125.71 | $362,140.61 | $6,212.70 vs $7,272.68 (10 trades) | 0.97 | -90.5% | 419.1% | Rejected |
| XRP | 2347 (78.1%) | 36 | $15,635.35 | $21,258.13 | $22,385.07 | $37,077.30 | $1,390.32 | $14,034.71 | $18,564.46 | $15,121.10 vs $17,268.99 (10 trades) | 0.42 | -83.4% | 464.8% | Rejected |

## Decisive checks

- Benchmark gate failed: 0/4 beat buy-and-hold, 1/4 beat DCA, 0/4 beat the BTC-momentum regime control.
- 2024+ holdout gate: 0/4 beat their own buy-and-hold benchmark.
- Concentration gate failed: 0/4 assets cleared the 20% top-PnL-block cap.
- The DJIA 200d trend state is a slow external regime variable, but it does not add deployable value beyond crypto's own benchmarks under this rule.

## Conclusion

- Dow Jones Industrial Average price-trend risk appetite does not produce a robust standalone crypto regime filter under this preregistered construction.
- Do not retest this same DJIA 200d-SMA risk-on filter without a fundamentally different confirmation or sizing mechanism.
