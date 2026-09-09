# RSP Equal-Weight S&P 500 ETF Trend Regime Validation

- **Experiment ID:** EXP-2026-09-09-RSPTREND-001
- **Verdict:** REJECTED
- **Primary rule:** Use real Yahoo Finance RSP adjusted daily closes as an external broad-market breadth risk-appetite filter: hold BTC/ETH/SOL/XRP long only when RSP adjusted close > prior-only 200-trading-day SMA; otherwise cash. Crypto action is lagged one daily bar.
- **Why new:** This tests traded equal-weight S&P 500 ETF trend specifically, distinct from already-rejected cap-weighted SP500/Nasdaq/DJIA, high-yield/IG credit, credit-spread z-score, rates, liquidity, FX, commodity, and crypto-native filters.
- **Real data:** Yahoo Finance RSP adjusted close cached at `data/macro_rsp_trend/rsp_1d.csv.gz` (2004-02-17 to 2026-07-27); cached Binance spot daily OHLCV; no synthetic/proxy inputs.

## Results

| Asset | Risk-on days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1d action lag | 2024+ final vs B&H | Sharpe | MaxDD | Top block PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| BTC | 2491 (79.6%) | 36 | $51,107.44 | $46,344.78 | $39,941.66 | $84,689.49 | $27,467.79 | $45,875.42 | $53,895.51 | $9,910.64 vs $15,032.99 (8 trades) | 0.63 | -65.7% | 127.0% | Rejected |
| ETH | 2491 (79.6%) | 36 | $24,118.26 | $25,741.27 | $34,753.86 | $127,304.60 | $2,738.38 | $21,649.20 | $18,936.87 | $4,675.57 vs $8,268.92 (8 trades) | 0.50 | -86.8% | 351.2% | Rejected |
| SOL | 1783 (81.9%) | 26 | $156,205.61 | $259,570.99 | $40,615.95 | $904,985.48 | $2,605,780.47 | $144,484.58 | $155,969.99 | $3,822.25 vs $7,272.68 (8 trades) | 0.93 | -87.5% | 231.8% | Rejected |
| XRP | 2368 (78.7%) | 36 | $15,745.45 | $21,258.13 | $22,385.07 | $37,077.30 | $34,620.61 | $14,133.54 | $13,813.48 | $11,039.27 vs $17,268.99 (8 trades) | 0.42 | -84.2% | 559.0% | Rejected |

## Decisive checks

- Benchmark gate failed: 1/4 beat buy-and-hold, 2/4 beat DCA, and 0/4 beat the BTC-momentum regime control.
- 2024+ holdout gate: 0/4 beat their own buy-and-hold benchmark.
- Concentration gate failed: 0/4 assets cleared the 20% top-PnL-block cap.
- The RSP 200d trend state is a slow external equity-breadth risk-appetite variable, but it does not add deployable value beyond crypto's own benchmarks under this rule.

## Conclusion

- RSP equal-weight S&P 500 breadth trend risk appetite does not produce a robust standalone crypto regime filter under this preregistered construction.
- Do not retest this same RSP 200d-SMA risk-on filter without a fundamentally different confirmation or sizing mechanism.
