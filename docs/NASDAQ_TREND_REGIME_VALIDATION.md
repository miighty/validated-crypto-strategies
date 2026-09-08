# Nasdaq Composite Trend Regime Validation

- **Experiment ID:** EXP-2026-09-08-NASDAQTREND-001
- **Verdict:** REJECTED
- **Primary rule:** Use real FRED NASDAQCOM daily closes as a growth-equity risk-appetite filter: hold BTC/ETH/SOL/XRP long only when Nasdaq Composite close > prior-only 200-trading-day SMA; otherwise cash. Crypto action is lagged one daily bar.
- **Why new:** This tests external growth-equity price trend specifically, distinct from already-rejected S&P 500 trend, equity implied-volatility overlays (VIX/VXN), credit/rate/liquidity macro overlays, and crypto-derived momentum/flow filters.
- **Real data:** FRED NASDAQCOM cached at `data/macro_nasdaq_trend/nasdaqcom_1d.csv.gz` (1971-11-19 to 2026-07-27); cached Binance spot daily OHLCV; no synthetic/proxy inputs.

## Results

| Asset | Risk-on days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1d action lag | 2024+ final vs B&H | Sharpe | MaxDD | Top block PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| BTC | 2479 (79.2%) | 20 | $104,096.80 | $46,344.78 | $39,941.66 | $84,689.49 | $92,377.72 | $98,034.64 | $100,642.88 | $12,054.67 vs $15,032.99 (5 trades) | 0.78 | -65.7% | 111.7% | Rejected |
| ETH | 2479 (79.2%) | 20 | $60,499.89 | $25,741.27 | $34,753.86 | $127,304.60 | $12,036.08 | $56,976.63 | $55,114.03 | $6,438.33 vs $8,268.92 (5 trades) | 0.65 | -86.8% | 151.6% | Rejected |
| SOL | 1698 (78.0%) | 11 | $935,999.19 | $259,570.99 | $40,615.95 | $904,985.48 | $93,837.90 | $905,615.15 | $1,000,293.80 | $6,014.27 vs $7,272.68 (5 trades) | 1.22 | -80.4% | 176.5% | Rejected |
| XRP | 2356 (78.4%) | 20 | $57,090.45 | $21,258.13 | $22,385.07 | $37,077.30 | $66,433.85 | $53,765.75 | $41,755.88 | $17,058.90 vs $17,268.99 (5 trades) | 0.59 | -71.2% | 208.1% | Rejected |

## Decisive checks

- Benchmark gate mixed: 4/4 beat buy-and-hold and DCA, but only 3/4 beat the BTC-momentum regime control.
- 2024+ holdout gate: 0/4 beat their own buy-and-hold benchmark.
- Concentration gate failed: 0/4 assets cleared the 20% top-PnL-block cap.
- The NASDAQCOM 200d trend state is a slow external growth-equity regime variable, but it does not add deployable value beyond crypto's own benchmarks under this rule.

## Conclusion

- Nasdaq Composite price-trend risk appetite does not produce a robust standalone crypto regime filter under this preregistered construction.
- Do not retest this same NASDAQCOM 200d-SMA risk-on filter without a fundamentally different confirmation or sizing mechanism.
