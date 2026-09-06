# VIX Risk-Off Overlay Validation

- **Experiment ID:** EXP-2026-09-06-VIXRISKOFF-001
- **Verdict:** REJECTED
- **Primary rule:** Use real FRED/CBOE VIXCLS as a risk-off overlay, not a panic-buy trigger: if VIX z-score >= +2.0 vs prior-only 60-trading-day baseline, exit BTC/ETH/SOL/XRP at the next daily open; stay cash until z < +1.0, then re-enter at the next daily open.
- **Why new:** This is the registry's explicitly allowed fundamentally different VIX role (risk-off/sizing overlay), not a retest of the rejected raw VIX fear-spike rebound entry.
- **Real data:** FRED VIXCLS cached at `data/macro_vix/vixcls_1d.csv.gz` (1991-11-26 to 2026-07-27); cached Binance spot daily OHLCV; no synthetic/proxy inputs.

## Results

| Asset | Risk-off days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1d action lag | 2024+ final vs B&H | Sharpe | MaxDD | Top block PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| BTC | 221 (7.1%) | 13 | $28,591.13 | $46,344.78 | $39,941.66 | $84,689.49 | $60,296.00 | $27,497.54 | $32,953.64 | $12,197.73 vs $15,032.99 (8 trades) | 0.52 | -81.2% | 96.8% | Rejected |
| ETH | 221 (7.1%) | 13 | $19,099.93 | $25,741.27 | $34,753.86 | $127,304.60 | $8,761.45 | $18,369.36 | $21,553.54 | $7,162.82 vs $8,268.92 (8 trades) | 0.51 | -94.0% | 205.7% | Rejected |
| SOL | 221 (10.2%) | 13 | $141,886.62 | $259,570.99 | $40,615.95 | $904,985.48 | $39,067.34 | $136,459.53 | $186,747.72 | $6,418.44 vs $7,272.68 (8 trades) | 0.93 | -95.7% | 198.3% | Rejected |
| XRP | 221 (7.3%) | 13 | $13,730.94 | $21,258.13 | $22,385.07 | $37,077.30 | $37,870.32 | $13,205.74 | $16,192.17 | $12,256.33 vs $17,268.99 (8 trades) | 0.44 | -85.0% | 849.4% | Rejected |

## Decisive checks

- Benchmark gate failed: 0/4 beat buy-and-hold, 1/4 beat DCA, 0/4 beat the BTC-momentum regime control.
- Concentration gate failed: 0/4 assets cleared the 20% top-PnL-block cap.
- Test partition gate failed: 0/4 assets beat their own 2024+ buy-and-hold benchmark.
- The overlay mostly removes exposure during high-volatility selloffs, but also misses large portions of the recovery; it is not a deployable standalone risk control on this rule.

## Conclusion

- Recasting VIX from a panic-buy entry into a risk-off overlay still does not add robust value against simple crypto baselines.
- This closes the obvious raw-VIX family in this repo: neither buying VIX panic spikes nor exiting during them passes the validation ladder.
