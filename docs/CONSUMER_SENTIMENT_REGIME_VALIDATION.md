# Consumer Sentiment Regime Validation

- **Experiment ID:** EXP-2026-09-08-UMCSENT-001
- **Verdict:** REJECTED
- **Primary rule:** Use real FRED UMCSENT monthly consumer sentiment as an external household-risk-appetite filter: long BTC/ETH/SOL/XRP only when UMCSENT > prior-only 12-month SMA and prior-only 3-month change > 0; otherwise cash. Crypto action is lagged one monthly print.
- **Why new:** This is the first consumer/household sentiment macro signal in the repo, distinct from equity trend, implied volatility, credit, rates, liquidity, DXY, and crypto-native sentiment/flow studies.
- **Real data:** FRED UMCSENT cached at `data/macro_consumer_sentiment/umcsent_1mo.csv.gz` (1956-11-01 to 2026-07-01); cached Binance spot daily OHLCV; no synthetic/proxy inputs.

## Results

| Asset | Risk-on days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1 print lag | 2024+ final vs B&H | Sharpe | MaxDD | Top block PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| BTC | 853 (27.3%) | 11 | $10,800.29 | $46,344.78 | $39,941.66 | $84,689.49 | $100,296.69 | $10,449.69 | $11,685.50 | $17,028.63 vs $15,032.99 (3 trades) | 0.22 | -79.6% | 460.8% | Rejected |
| ETH | 853 (27.3%) | 11 | $9,745.55 | $25,741.27 | $34,753.86 | $127,304.60 | $29,421.63 | $9,429.19 | $11,592.68 | $15,599.73 vs $8,268.92 (3 trades) | 0.24 | -86.3% | 1578.5% | Rejected |
| SOL | 549 (25.2%) | 6 | $57,550.94 | $259,570.99 | $40,615.95 | $904,985.48 | $5,771.95 | $56,524.29 | $100,046.69 | $16,288.72 vs $7,272.68 (3 trades) | 0.81 | -58.1% | 52.3% | Rejected |
| XRP | 820 (27.3%) | 11 | $5,354.35 | $21,258.13 | $22,385.07 | $37,077.30 | $3,121.49 | $5,180.53 | $5,454.06 | $15,452.80 vs $17,268.99 (3 trades) | -0.04 | -92.1% | 42.2% | Rejected |

## Decisive checks

- Benchmark gate failed: 0/4 beat buy-and-hold, 1/4 beat DCA, 0/4 beat the BTC-momentum regime control.
- 2024+ holdout gate: 3/4 beat their own buy-and-hold benchmark.
- Concentration gate failed: 0/4 assets cleared the 20% top-PnL-block cap.
- Monthly consumer sentiment is too slow and sparse to add deployable timing value under this standalone construction.

## Conclusion

- Consumer-sentiment improvement does not produce a robust standalone crypto risk-on filter.
- Do not retest this same UMCSENT 12-month-SMA / 3-month-change rule without a fundamentally different confirmation or sizing mechanism.
