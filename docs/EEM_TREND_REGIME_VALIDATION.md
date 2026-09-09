# EEM Emerging-Market Equity Trend Regime Validation

- **Experiment ID:** EXP-2026-09-09-EEMTREND-001
- **Verdict:** REJECTED
- **Primary rule:** Use real Yahoo Finance EEM adjusted daily closes as an external emerging-market/global-risk appetite filter: hold BTC/ETH/SOL/XRP long only when EEM adjusted close > prior-only 200-trading-day SMA; otherwise cash. Crypto action is lagged one daily bar.
- **Why new:** This tests traded emerging-market equity trend specifically, distinct from already-rejected U.S. equity-index, small-cap, credit, rates, liquidity, FX, commodity, and crypto-native filters.
- **Real data:** Yahoo Finance EEM adjusted close cached at `data/macro_eem_trend/eem_1d.csv.gz` (2004-01-29 to 2026-07-27); cached Binance spot daily OHLCV; no synthetic/proxy inputs.

## Results

| Asset | Risk-on days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1d action lag | 2024+ final vs B&H | Sharpe | MaxDD | Top block PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| BTC | 1983 (63.4%) | 37 | $103,595.73 | $46,344.78 | $39,941.66 | $84,689.49 | $12,222.84 | $92,711.78 | $81,938.56 | $12,594.94 vs $15,032.99 (9 trades) | 0.80 | -61.3% | 124.9% | Rejected |
| ETH | 1983 (63.4%) | 37 | $188,950.11 | $25,741.27 | $34,753.86 | $127,304.60 | $43,850.31 | $169,098.67 | $138,408.53 | $10,614.70 vs $8,268.92 (9 trades) | 0.85 | -73.4% | 69.8% | Rejected |
| SOL | 1497 (68.8%) | 18 | $135,624.73 | $259,570.99 | $40,615.95 | $904,985.48 | $334,977.45 | $128,495.19 | $90,801.94 | $5,214.47 vs $7,272.68 (9 trades) | 0.90 | -84.0% | 238.4% | Rejected |
| XRP | 1861 (61.9%) | 36 | $25,359.83 | $21,258.13 | $22,385.07 | $37,077.30 | $2,910.02 | $22,763.67 | $21,622.89 | $11,897.76 vs $17,268.99 (9 trades) | 0.52 | -76.1% | 445.5% | Rejected |

## Decisive checks

- Benchmark gate failed: 3/4 beat buy-and-hold, 4/4 beat DCA, and 2/4 beat the BTC-momentum regime control.
- 2024+ holdout gate: 1/4 beat their own buy-and-hold benchmark.
- Concentration gate failed: 0/4 assets cleared the 20% top-PnL-block cap.
- The EEM 200d trend state is a slow external global-risk variable, but it does not add deployable value beyond crypto's own benchmarks under this rule.

## Conclusion

- EEM emerging-market equity trend risk appetite does not produce a robust standalone crypto regime filter under this preregistered construction.
- Do not retest this same EEM 200d-SMA risk-on filter without a fundamentally different confirmation or sizing mechanism.
