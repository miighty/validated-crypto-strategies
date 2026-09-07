# Nasdaq-100 VXN Risk-Off Overlay Validation

- **Experiment ID:** EXP-2026-09-07-VXNRISKOFF-001
- **Verdict:** REJECTED
- **Primary rule:** Use real FRED/CBOE VXNCLS as a tech-equity stress risk-off overlay: if VXN z-score >= +2.0 vs a prior-only 60-trading-day baseline, exit BTC/ETH/SOL/XRP at the next daily open; stay cash until z < +1.0, then re-enter at the next daily open.
- **Why new:** This tests Nasdaq-100 implied-volatility stress specifically, distinct from the already-rejected VIX broad-equity, GVZ gold-vol, OVX oil-vol, DVOL crypto-vol, and macro-rate/credit/liquidity overlays.
- **Real data:** FRED VXNCLS cached at `data/macro_vxn/vxncls_1d.csv.gz` (2001-05-01 to 2026-07-27); cached Binance spot daily OHLCV; no synthetic/proxy inputs.

## Results

| Asset | Risk-off days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1d action lag | 2024+ final vs B&H | Sharpe | MaxDD | Top block PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| BTC | 435 (13.9%) | 49 | $24,995.76 | $46,344.78 | $39,941.66 | $84,689.49 | $15,083.21 | $21,578.68 | $25,573.64 | $12,479.04 vs $15,032.99 (15 trades) | 0.48 | -82.4% | 122.7% | Rejected |
| ETH | 435 (13.9%) | 49 | $14,149.69 | $25,741.27 | $34,753.86 | $127,304.60 | $17,562.26 | $12,215.33 | $14,198.14 | $8,130.77 vs $8,268.92 (15 trades) | 0.43 | -92.8% | 523.8% | Rejected |
| SOL | 291 (13.4%) | 37 | $143,224.30 | $259,570.99 | $40,615.95 | $904,985.48 | $147,006.19 | $128,176.91 | $136,720.56 | $5,516.75 vs $7,272.68 (15 trades) | 0.92 | -93.4% | 166.1% | Rejected |
| XRP | 405 (13.5%) | 47 | $9,543.11 | $21,258.13 | $22,385.07 | $37,077.30 | $29,807.19 | $8,288.08 | $9,225.53 | $10,832.06 vs $17,268.99 (15 trades) | 0.35 | -85.0% | 5010.0% | Rejected |

## Decisive checks

- Benchmark gate failed: 0/4 beat buy-and-hold, 1/4 beat DCA, 0/4 beat the BTC-momentum regime control.
- 2024+ holdout gate: 0/4 beat their own buy-and-hold benchmark.
- Concentration gate failed: 0/4 assets cleared the 20% top-PnL-block cap.
- This is sparse regime evidence, not a deployable risk control; the overlay avoids some stress windows but is dominated by simple crypto momentum and concentration effects.

## Conclusion

- Nasdaq-100 implied-volatility stress does not add robust standalone value as a crypto risk-off overlay under this preregistered rule.
- Do not retest this same VXN z-score/hysteresis overlay without a fundamentally different confirmation or sizing mechanism.
