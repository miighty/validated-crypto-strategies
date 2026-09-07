# 10Y Breakeven-Inflation Growth-Scare Risk-Off Validation

- **Experiment ID:** EXP-2026-09-07-BREAKEVEN-RISKOFF-001
- **Verdict:** REJECTED
- **Primary rule:** Use real FRED `T10YIE` 10-year breakeven inflation as an external growth/liquidity stress overlay; if z-score <= -2.0 versus a prior-only 252-trading-day baseline, exit BTC/ETH/SOL/XRP at the next daily open; stay cash until z > -1.0, then re-enter at the next daily open.
- **Why new:** First breakeven-inflation / market-implied inflation-expectations signal in this repo; distinct from real yields (`DFII10`), nominal yield-curve slope, DXY, VIX, BAA credit spreads, Fed balance sheet, M2, and NFCI.
- **Real data:** FRED T10YIE cached at `data/macro_breakeven_inflation/t10yie_1d.csv.gz` (2004-01-06 to 2026-07-27); cached Binance spot daily OHLCV; no synthetic/proxy inputs.

## Results

| Asset | Risk-off days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1d action lag | 2024+ final vs B&H | Sharpe | Sortino | MaxDD | Top block PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- |
| BTC | 421 (13.5%) | 8 | $35,334.48 | $46,344.78 | $39,941.66 | $84,689.49 | $32,261.85 | $34,496.54 | $40,006.60 | $12,493.98 vs $15,032.99 (3 trades) | 0.55 | 0.80 | -78.0% | 102.2% | Rejected |
| ETH | 421 (13.5%) | 8 | $24,623.34 | $25,741.27 | $34,753.86 | $127,304.60 | $21,693.43 | $24,039.41 | $25,723.33 | $6,986.08 vs $8,268.92 (3 trades) | 0.52 | 0.75 | -92.7% | 145.2% | Rejected |
| SOL | 96 (4.4%) | 4 | $229,037.88 | $259,570.99 | $40,615.95 | $904,985.48 | $247,932.53 | $226,305.83 | $206,792.75 | $5,719.63 vs $7,272.68 (3 trades) | 1.00 | 1.59 | -95.8% | 193.6% | Rejected |
| XRP | 421 (14.0%) | 8 | $30,614.90 | $21,258.13 | $22,385.07 | $37,077.30 | $23,489.68 | $29,888.89 | $33,009.43 | $14,270.72 vs $17,268.99 (3 trades) | 0.52 | 0.89 | -83.2% | 71.4% | Rejected |

## Decisive checks

- Benchmark gate failed: 1/4 beat buy-and-hold, 2/4 beat DCA, 0/4 beat the BTC-momentum regime control.
- 2024+ holdout gate: 0/4 beat buy-and-hold in the 2024+ partition.
- Concentration gate failed: 0/4 assets cleared the 20% top-PnL-block cap.
- Breakeven-inflation growth-scare episodes are sparse and do not provide a deployable standalone crypto timing overlay after costs and benchmark comparison.

## Conclusion

- The 10Y breakeven-inflation risk-off overlay is not deployable as tested.
- This closes the simple T10YIE downside-z-score growth-scare overlay; do not retest the same breakeven threshold/hysteresis rule without a fundamentally different mechanism or confirmation signal.
