# NFCI Financial-Conditions Risk-Off Overlay Validation

- **Experiment ID:** EXP-2026-09-06-NFCIRISKOFF-001
- **Verdict:** REJECTED
- **Primary rule:** If real FRED Chicago Fed National Financial Conditions Index (`NFCI`) z-score >= +2.0 vs a prior-only 156-week baseline, exit BTC/ETH/SOL/XRP at the next daily open; stay cash until z < +1.0, then re-enter at the next daily open.
- **Why new:** First broad financial-conditions index in this repo; distinct from raw VIX volatility, DXY dollar trend, BAA credit spread, and Treasury yield-curve overlays.
- **Real data:** FRED NFCI cached at `data/macro_financial_conditions/nfci_1w.csv.gz` (1974-01-04 to 2026-07-24); cached Binance spot daily OHLCV; no synthetic/proxy inputs.

## Results

| Asset | Risk-off days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1w action lag | 2024+ final vs B&H | Sharpe | MaxDD | Top block PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| BTC | 112 (3.6%) | 2 | $43,434.13 | $46,344.78 | $39,941.66 | $84,689.49 | $39,127.19 | $43,174.31 | $45,232.58 | $15,032.99 vs $15,032.99 (1 trades) | 0.59 | -81.2% | 110.7% | Rejected |
| ETH | 112 (3.6%) | 2 | $25,272.42 | $25,741.27 | $34,753.86 | $127,304.60 | $29,108.91 | $25,121.24 | $25,210.47 | $8,268.92 vs $8,268.92 (1 trades) | 0.54 | -94.0% | 145.2% | Rejected |
| SOL | 0 (0.0%) | 1 | $259,570.99 | $259,570.99 | $40,615.95 | $904,985.48 | $259,570.99 | $258,793.44 | $259,570.99 | $7,272.68 vs $7,272.68 (1 trades) | 1.02 | -96.3% | 100.0% | Rejected |
| XRP | 112 (3.7%) | 2 | $26,644.13 | $21,258.13 | $22,385.07 | $37,077.30 | $18,837.41 | $26,484.75 | $27,907.89 | $17,268.99 vs $17,268.99 (1 trades) | 0.52 | -83.2% | 131.5% | Rejected |

## Decisive checks

- Benchmark gate: 2/4 beat buy-and-hold, 3/4 beat DCA, 0/4 beat the BTC-momentum regime control.
- 2024+ holdout gate: 0/4 beat buy-and-hold in the 2024+ partition.
- Concentration gate: 0/4 assets cleared the 20% top-PnL-block cap.
- NFCI stress episodes are too sparse and lagging for this crypto timing construction; where the overlay helps, the result is still dominated by one macro-crisis block.

## Conclusion

- The broad financial-conditions stress overlay is not deployable as tested.
- This closes the simple NFCI z-score risk-off construction; do not retest the same z>=2 / z<1 hysteresis rule without a fundamentally different mechanism or sizing rule.
