# IWM Small-Cap Trend Regime Validation

- **Experiment ID:** EXP-2026-09-08-IWMTREND-001
- **Verdict:** REJECTED
- **Primary rule:** Use real Yahoo Finance IWM adjusted daily closes as a small-cap-equity risk-appetite filter: hold BTC/ETH/SOL/XRP long only when IWM adjusted close > prior-only 200-trading-day SMA; otherwise cash. Crypto action is lagged one daily bar.
- **Why new:** This tests external small-cap equity price trend specifically, distinct from already-rejected SP500/Nasdaq/DJIA large-cap equity trend filters, equity implied-volatility overlays (VIX/VXN), credit/rate/liquidity macro overlays, and crypto-derived momentum/flow filters.
- **Real data:** Yahoo Finance IWM adjusted close cached at `data/macro_iwm_trend/iwm_1d.csv.gz` (2001-03-14 to 2026-07-27); cached Binance spot daily OHLCV; no synthetic/proxy inputs.

## Results

| Asset | Risk-on days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1d action lag | 2024+ final vs B&H | Sharpe | MaxDD | Top block PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| BTC | 2076 (66.3%) | 39 | $47,874.83 | $46,344.78 | $39,941.66 | $84,689.49 | $56,870.34 | $42,588.71 | $71,823.72 | $12,493.57 vs $15,032.99 (5 trades) | 0.62 | -65.7% | 128.1% | Rejected |
| ETH | 2076 (66.3%) | 39 | $30,565.00 | $25,741.27 | $34,753.86 | $127,304.60 | $10,319.04 | $27,190.15 | $41,600.69 | $7,594.35 vs $8,268.92 (5 trades) | 0.53 | -88.0% | 215.6% | Rejected |
| SOL | 1507 (69.2%) | 22 | $322,660.90 | $259,570.99 | $40,615.95 | $904,985.48 | $2,189,484.88 | $302,052.73 | $548,510.11 | $6,835.14 vs $7,272.68 (5 trades) | 1.05 | -77.7% | 121.8% | Rejected |
| XRP | 1953 (64.9%) | 39 | $28,932.00 | $21,258.13 | $22,385.07 | $37,077.30 | $3,059.83 | $25,737.46 | $37,616.26 | $17,470.84 vs $17,268.99 (5 trades) | 0.48 | -78.0% | 236.7% | Rejected |

## Decisive checks

- Deployability gate failed despite B&H wins: 4/4 beat buy-and-hold, 3/4 beat DCA, but 0/4 beat the BTC-momentum regime control.
- 2024+ holdout gate: 1/4 beat their own buy-and-hold benchmark.
- Concentration gate failed: 0/4 assets cleared the 20% top-PnL-block cap.
- The IWM 200d trend state is a slow external regime variable, but it does not add deployable value beyond crypto's own benchmarks under this rule.

## Conclusion

- IWM small-cap price-trend risk appetite does not produce a robust standalone crypto regime filter under this preregistered construction.
- Do not retest this same IWM 200d-SMA risk-on filter without a fundamentally different confirmation or sizing mechanism.
