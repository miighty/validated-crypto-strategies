# 10Y Real-Yield Risk-Off Overlay Validation

- **Experiment ID:** EXP-2026-09-07-REALYIELD-RISKOFF-001
- **Verdict:** REJECTED
- **Primary rule:** Use real FRED `DFII10` 10-year TIPS real yield as an external macro-liquidity stress overlay; if z-score >= +2.0 versus a prior-only 252-trading-day baseline, exit BTC/ETH/SOL/XRP at the next daily open; stay cash until z < +1.0, then re-enter at the next daily open.
- **Why new:** First real-yield/TIPS signal in this repo; distinct from nominal yield-curve slope, DXY, VIX, credit spreads, Fed balance sheet, M2, NFCI, and crypto-native flow/positioning data.
- **Real data:** FRED DFII10 cached at `data/macro_real_yields/dfii10_1d.csv.gz` (2004-01-06 to 2026-07-27); cached Binance spot daily OHLCV; no synthetic/proxy inputs.

## Results

| Asset | Risk-off days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1d action lag | 2024+ final vs B&H | Sharpe | Sortino | MaxDD | Top block PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- |
| BTC | 726 (23.2%) | 8 | $242,261.76 | $46,344.78 | $39,941.66 | $84,689.49 | $19,537.40 | $236,516.66 | $203,069.92 | $17,244.87 vs $15,032.99 (2 trades) | 0.95 | 1.41 | -63.3% | 81.8% | Rejected |
| ETH | 726 (23.2%) | 8 | $310,623.40 | $25,741.27 | $34,753.86 | $127,304.60 | $13,795.50 | $303,257.15 | $284,355.94 | $9,878.00 vs $8,268.92 (2 trades) | 0.91 | 1.36 | -69.6% | 76.1% | Rejected |
| SOL | 505 (23.2%) | 6 | $597,731.44 | $259,570.99 | $40,615.95 | $904,985.48 | $1,199,399.79 | $587,068.48 | $439,972.12 | $6,797.22 vs $7,272.68 (2 trades) | 1.15 | 1.89 | -75.1% | 191.6% | Rejected |
| XRP | 625 (20.8%) | 7 | $58,026.83 | $21,258.13 | $22,385.07 | $37,077.30 | $5,245.44 | $56,820.97 | $56,473.53 | $16,115.71 vs $17,268.99 (2 trades) | 0.67 | 1.14 | -71.6% | 196.0% | Rejected |

## Decisive checks

- Benchmark gate was mixed: 4/4 beat buy-and-hold and DCA, but only 3/4 beat the BTC-momentum regime control.
- 2024+ holdout gate: 2/4 beat buy-and-hold in the 2024+ partition.
- Concentration gate failed: 0/4 assets cleared the 20% top-PnL-block cap.
- Real-yield stress episodes remove exposure during some macro tightening windows, but the rule misses too much crypto upside and does not beat simple crypto-native momentum.

## Conclusion

- The 10Y real-yield risk-off overlay is not deployable as tested.
- This closes the simple DFII10 z-score stress overlay; do not retest the same real-yield threshold/hysteresis rule without a fundamentally different mechanism or confirmation signal.
