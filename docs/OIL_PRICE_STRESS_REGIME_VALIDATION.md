# WTI Oil Price Stress Regime Validation

- **Experiment ID:** EXP-2026-09-08-OILPRICESTRESS-001
- **Verdict:** REJECTED
- **Primary rule:** Use real FRED DCOILWTICO daily WTI spot prices as an external energy/inflation stress filter: hold BTC/ETH/SOL/XRP long only when WTI is **not** above its prior-only 200-trading-day SMA with positive prior-only 60-trading-day return. Crypto action is lagged one daily bar.
- **Why new:** This tests oil-price trend/stress itself, distinct from the already-rejected oil-implied-volatility (OVX) overlay and other macro credit/rate/equity/vol filters.
- **Real data:** FRED DCOILWTICO cached at `data/macro_oil_price_stress/dcoilwtico_1d.csv.gz` (1986-10-17 to 2026-07-27); cached Binance spot daily OHLCV; no synthetic/proxy inputs.

## Results

| Asset | Risk-on days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1d action lag | 2024+ final vs B&H | Sharpe | MaxDD | Top block PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| BTC | 1836 (58.7%) | 57 | $37,639.04 | $46,344.78 | $39,941.66 | $84,689.49 | $4,068.34 | $31,722.97 | $18,986.39 | $13,963.75 vs $15,032.99 (19 trades) | 0.57 | -63.4% | 66.6% | Rejected |
| ETH | 1836 (58.7%) | 57 | $27,666.43 | $25,741.27 | $34,753.86 | $127,304.60 | $44,909.01 | $23,317.84 | $9,242.22 | $10,223.28 vs $8,268.92 (19 trades) | 0.51 | -78.6% | 61.3% | Rejected |
| SOL | 1264 (58.1%) | 40 | $13,391.55 | $259,570.99 | $40,615.95 | $904,985.48 | $288,651.59 | $11,877.23 | $4,909.60 | $5,631.17 vs $7,272.68 (19 trades) | 0.42 | -79.9% | 489.4% | Rejected |
| XRP | 1834 (61.0%) | 56 | $50,135.81 | $21,258.13 | $22,385.07 | $37,077.30 | $88,029.99 | $42,382.46 | $12,969.25 | $20,257.38 vs $17,268.99 (19 trades) | 0.61 | -72.3% | 203.6% | Rejected |

## Decisive checks

- Benchmark gate failed: 2/4 beat buy-and-hold, 1/4 beat DCA, 1/4 beat the BTC-momentum regime control.
- 2024+ holdout gate: 2/4 beat their own buy-and-hold benchmark.
- Concentration gate failed: 0/4 assets cleared the 20% top-PnL-block cap.
- The WTI price-stress state is real external macro data, but it does not add deployable value beyond crypto's own benchmarks under this rule.

## Conclusion

- WTI crude oil price stress does not produce a robust standalone crypto risk-off filter under this preregistered construction.
- Do not retest this same WTI 200d-SMA / 60d-return risk-off filter without a fundamentally different confirmation or sizing mechanism.
