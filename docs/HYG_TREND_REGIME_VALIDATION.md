# HYG High-Yield Credit Trend Regime Validation

- **Experiment ID:** EXP-2026-09-09-HYGTREND-001
- **Verdict:** REJECTED
- **Primary rule:** Use real Yahoo Finance HYG adjusted daily closes as a traded high-yield credit risk-appetite filter: hold BTC/ETH/SOL/XRP long only when HYG adjusted close > prior-only 200-trading-day SMA; otherwise cash. Crypto action is lagged one daily bar.
- **Why new:** This tests traded high-yield credit price trend specifically, distinct from already-rejected high-yield OAS level, BAA credit spread, equity-index, rates, liquidity, FX, commodity, and crypto-native filters.
- **Real data:** Yahoo Finance HYG adjusted close cached at `data/macro_hyg_trend/hyg_1d.csv.gz` (2008-01-25 to 2026-07-27); cached Binance spot daily OHLCV; no synthetic/proxy inputs.

## Results

| Asset | Risk-on days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1d action lag | 2024+ final vs B&H | Sharpe | MaxDD | Top block PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| BTC | 2517 (80.4%) | 36 | $77,589.65 | $46,344.78 | $39,941.66 | $84,689.49 | $36,885.44 | $69,646.57 | $152,457.02 | $13,012.80 vs $15,032.99 (4 trades) | 0.72 | -71.5% | 89.2% | Rejected |
| ETH | 2517 (80.4%) | 36 | $45,537.82 | $25,741.27 | $34,753.86 | $127,304.60 | $8,362.76 | $40,875.98 | $111,932.71 | $7,007.86 vs $8,268.92 (4 trades) | 0.60 | -88.5% | 182.6% | Rejected |
| SOL | 1802 (82.8%) | 14 | $796,923.93 | $259,570.99 | $40,615.95 | $904,985.48 | $779,145.89 | $764,146.10 | $1,253,296.06 | $5,615.22 vs $7,272.68 (4 trades) | 1.19 | -81.7% | 114.2% | Rejected |
| XRP | 2457 (81.7%) | 28 | $15,739.51 | $21,258.13 | $22,385.07 | $37,077.30 | $5,341.25 | $14,471.39 | $41,369.19 | $14,962.09 vs $17,268.99 (4 trades) | 0.50 | -77.5% | 389.4% | Rejected |

## Decisive checks

- Benchmark gate failed: 3/4 beat buy-and-hold, 3/4 beat DCA, and 0/4 beat the BTC-momentum regime control.
- 2024+ holdout gate: 0/4 beat their own buy-and-hold benchmark.
- Concentration gate failed: 0/4 assets cleared the 20% top-PnL-block cap.
- The HYG 200d trend state is a slow external credit-risk variable, but it does not add deployable value beyond crypto's own benchmarks under this rule.

## Conclusion

- HYG high-yield credit price-trend risk appetite does not produce a robust standalone crypto regime filter under this preregistered construction.
- Do not retest this same HYG 200d-SMA risk-on filter without a fundamentally different confirmation or sizing mechanism.
