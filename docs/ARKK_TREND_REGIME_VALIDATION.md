# ARKK Speculative-Growth Equity Trend Regime Validation

- **Experiment ID:** EXP-2026-09-09-ARKKTREND-001
- **Verdict:** REJECTED
- **Primary rule:** Use real Yahoo Finance ARKK adjusted daily closes as an external speculative-growth risk-appetite filter: hold BTC/ETH/SOL/XRP long only when ARKK adjusted close > prior-only 200-trading-day SMA; otherwise cash. Crypto action is lagged one daily bar.
- **Why new:** This tests traded speculative-growth/innovation-equity trend specifically, distinct from already-rejected broad U.S. equity, small-cap, emerging-market, credit, rates, liquidity, FX, commodity, and crypto-native filters.
- **Real data:** Yahoo Finance ARKK adjusted close cached at `data/macro_arkk_trend/arkk_1d.csv.gz` (2015-08-19 to 2026-07-27); cached Binance spot daily OHLCV; no synthetic/proxy inputs.

## Results

| Asset | Risk-on days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1d action lag | 2024+ final vs B&H | Sharpe | MaxDD | Top block PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| BTC | 1880 (60.1%) | 57 | $115,614.75 | $46,344.78 | $39,941.66 | $84,689.49 | $36,782.41 | $97,442.52 | $40,638.39 | $12,444.85 vs $15,032.99 (24 trades) | 0.84 | -67.5% | 57.6% | Rejected |
| ETH | 1880 (60.1%) | 57 | $99,209.93 | $25,741.27 | $34,753.86 | $127,304.60 | $59,668.15 | $83,616.20 | $22,049.85 | $8,791.21 vs $8,268.92 (24 trades) | 0.73 | -87.4% | 91.1% | Rejected |
| SOL | 1146 (52.6%) | 45 | $590,929.95 | $259,570.99 | $40,615.95 | $904,985.48 | $21,857.06 | $516,304.54 | $164,932.77 | $7,376.48 vs $7,272.68 (24 trades) | 1.18 | -79.5% | 110.2% | Rejected |
| XRP | 1757 (58.4%) | 57 | $89,110.71 | $21,258.13 | $22,385.07 | $37,077.30 | $23,741.10 | $75,104.36 | $28,557.67 | $22,567.77 vs $17,268.99 (24 trades) | 0.62 | -81.1% | 173.4% | Rejected |

## Decisive checks

- Benchmark gate was mixed: 4/4 beat buy-and-hold and DCA, but only 2/4 beat the BTC-momentum regime control.
- 2024+ holdout gate: 3/4 beat their own buy-and-hold benchmark.
- Concentration gate failed: 0/4 assets cleared the 20% top-PnL-block cap.
- The ARKK 200d trend state is a slow external speculative-risk variable, but it does not add deployable value beyond crypto's own benchmarks under this rule.

## Conclusion

- ARKK speculative-growth equity trend risk appetite does not produce a robust standalone crypto regime filter under this preregistered construction.
- Do not retest this same ARKK 200d-SMA risk-on filter without a fundamentally different confirmation or sizing mechanism.
