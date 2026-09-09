# TLT Long-Duration Treasury Trend Regime Validation

- **Experiment ID:** EXP-2026-09-09-TLTTREND-001
- **Verdict:** REJECTED
- **Primary rule:** Use real Yahoo Finance TLT adjusted daily closes as a long-duration Treasury/easing-liquidity filter: hold BTC/ETH/SOL/XRP long only when TLT adjusted close > prior-only 200-trading-day SMA; otherwise cash. Crypto action is lagged one daily bar.
- **Why new:** This tests traded long-duration Treasury price trend specifically, distinct from already-rejected real-yield level, yield-curve inversion, Fed-liquidity, equity-index, commodity, credit-spread, FX, and crypto-native filters.
- **Real data:** Yahoo Finance TLT adjusted close cached at `data/macro_tlt_trend/tlt_1d.csv.gz` (2003-05-15 to 2026-07-27); cached Binance spot daily OHLCV; no synthetic/proxy inputs.

## Results

| Asset | Risk-on days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1d action lag | 2024+ final vs B&H | Sharpe | MaxDD | Top block PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| BTC | 1502 (48.0%) | 60 | $36,817.98 | $46,344.78 | $39,941.66 | $84,689.49 | $10,352.59 | $30,752.93 | $51,097.82 | $8,623.19 vs $15,032.99 (28 trades) | 0.58 | -63.3% | 83.4% | Rejected |
| ETH | 1502 (48.0%) | 60 | $33,601.38 | $25,741.27 | $34,753.86 | $127,304.60 | $38,868.87 | $28,066.20 | $62,572.18 | $5,175.03 vs $8,268.92 (28 trades) | 0.54 | -70.8% | 104.5% | Rejected |
| SOL | 814 (37.4%) | 53 | $27,682.76 | $259,570.99 | $40,615.95 | $904,985.48 | $60,801.40 | $23,613.27 | $64,022.35 | $5,166.18 vs $7,272.68 (28 trades) | 0.54 | -76.7% | 160.2% | Rejected |
| XRP | 1481 (49.3%) | 58 | $6,626.49 | $21,258.13 | $22,385.07 | $37,077.30 | $25,626.20 | $5,568.21 | $13,221.29 | $7,603.90 vs $17,268.99 (28 trades) | 0.21 | -72.3% | 197.6% | Rejected |

## Decisive checks

- Benchmark gate failed: 1/4 beat buy-and-hold, 0/4 beat DCA, and 0/4 beat the BTC-momentum regime control.
- 2024+ holdout gate: 0/4 beat their own buy-and-hold benchmark.
- Concentration gate failed: 0/4 assets cleared the 20% top-PnL-block cap.
- The TLT 200d trend state is a slow external duration/liquidity variable, but it does not add deployable value beyond crypto's own benchmarks under this rule.

## Conclusion

- TLT long-duration Treasury price-trend risk appetite does not produce a robust standalone crypto regime filter under this preregistered construction.
- Do not retest this same TLT 200d-SMA risk-on filter without a fundamentally different confirmation or sizing mechanism.
