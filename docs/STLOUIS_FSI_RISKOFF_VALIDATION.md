# St. Louis Fed Financial Stress Index Risk-Off Overlay Validation

- **Experiment ID:** EXP-2026-09-07-STLFSIRISKOFF-001
- **Verdict:** REJECTED
- **Primary rule:** If real FRED St. Louis Fed Financial Stress Index (`STLFSI4`) z-score >= +2.0 vs a prior-only 156-week baseline, exit BTC/ETH/SOL/XRP at the next daily open; stay cash until z < +1.0, then re-enter at the next daily open.
- **Why new:** First St. Louis Fed stress-index overlay in this repo; distinct from NFCI, credit spreads, VIX, DXY, real yields, breakevens, M2, WALCL, and Treasury yield-curve signals.
- **Real data:** FRED STLFSI4 cached at `data/macro_stress/stlouis_fsi_1w.csv.gz` (2012-12-28 to 2026-07-24 after the 156-week prior-only warmup; raw FRED graph export provides 2010 onward); cached Binance spot daily OHLCV; no synthetic/proxy inputs.

## Results

| Asset | Risk-off days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1d action lag | 2024+ final vs B&H | Sharpe | MaxDD | Top block PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| BTC | 105 (3.4%) | 4 | $45,321.47 | $46,344.78 | $39,941.66 | $84,689.49 | $24,020.10 | $44,780.86 | $19,369.33 | $13,547.46 vs $15,032.99 (2 trades) | 0.60 | -81.2% | 168.3% | Rejected |
| ETH | 105 (3.4%) | 4 | $28,217.41 | $25,741.27 | $34,753.86 | $127,304.60 | $27,213.46 | $27,880.82 | $10,573.00 | $7,377.60 vs $8,268.92 (2 trades) | 0.55 | -94.0% | 125.0% | Rejected |
| SOL | 7 (0.3%) | 2 | $228,749.32 | $259,570.99 | $40,615.95 | $904,985.48 | $269,884.60 | $227,380.92 | $261,709.91 | $6,409.12 vs $7,272.68 (2 trades) | 1.01 | -96.3% | 211.1% | Rejected |
| XRP | 105 (3.5%) | 4 | $23,058.87 | $21,258.13 | $22,385.07 | $37,077.30 | $10,858.90 | $22,783.81 | $14,244.92 | $16,142.79 vs $17,268.99 (2 trades) | 0.50 | -83.2% | 330.7% | Rejected |

## Decisive checks

- Benchmark gate failed: 2/4 beat buy-and-hold, 3/4 beat DCA, 0/4 beat the BTC-momentum regime control.
- Concentration gate failed: 0/4 assets cleared the 20% top-PnL-block cap.
- Test partition gate failed: 0/4 assets beat their own 2024+ buy-and-hold benchmark.
- St. Louis FSI stress is too sparse and lagging as a crypto de-risking overlay in this construction.

## Conclusion

- St. Louis FSI stress does not add deployable standalone timing value against simple crypto baselines.
- This rejects the simplest STLFSI4 z>=2 / z<1 hysteresis construction; do not retest without a fundamentally different sizing or confirmation rule.
