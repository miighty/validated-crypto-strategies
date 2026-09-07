# Gold-Implied-Volatility Risk-Off Validation

- **Experiment ID:** EXP-2026-09-07-GOLDVOLRISKOFF-001
- **Verdict:** REJECTED
- **Primary rule:** Use real FRED `GVZCLS` CBOE Gold ETF Volatility Index as an external safe-haven/stress overlay; if z-score >= +2.0 versus a prior-only 252-trading-day baseline, exit BTC/ETH/SOL/XRP at the next daily open; stay cash until z < +1.0, then re-enter at the next daily open.
- **Why new:** First gold-implied-volatility / precious-metals stress signal in this repo; distinct from VIX, DVOL, DXY, real yields, breakevens, credit spreads, Fed liquidity, M2, NFCI/STLFSI, and Treasury yield-curve signals.
- **Real data:** FRED GVZCLS cached at `data/macro_gold_vol/gvzcls_1d.csv.gz` (2009-06-03 to 2026-07-27); cached Binance spot daily OHLCV; no synthetic/proxy inputs.

## Results

| Asset | Risk-off days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1d action lag | 2024+ final vs B&H | Sharpe | Sortino | MaxDD | Top block PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- |
| BTC | 451 (14.4%) | 15 | $51,480.25 | $46,344.78 | $39,941.66 | $84,689.49 | $33,506.80 | $49,214.98 | $61,650.71 | $18,025.08 vs $15,032.99 (8 trades) | 0.63 | 0.91 | -84.9% | 68.9% | Rejected |
| ETH | 451 (14.4%) | 15 | $33,593.51 | $25,741.27 | $34,753.86 | $127,304.60 | $2,639.04 | $32,115.31 | $40,073.88 | $9,142.55 vs $8,268.92 (8 trades) | 0.56 | 0.82 | -94.4% | 226.6% | Rejected |
| SOL | 239 (11.0%) | 10 | $231,098.62 | $259,570.99 | $40,615.95 | $904,985.48 | $97,337.55 | $224,268.59 | $320,371.02 | $9,530.84 vs $7,272.68 (8 trades) | 1.00 | 1.59 | -97.4% | 162.0% | Rejected |
| XRP | 434 (14.4%) | 14 | $38,080.24 | $21,258.13 | $22,385.07 | $37,077.30 | $20,559.97 | $36,513.98 | $41,395.41 | $21,779.71 vs $17,268.99 (8 trades) | 0.55 | 0.93 | -84.1% | 138.7% | Rejected |

## Decisive checks

- Benchmark gate failed: 3/4 beat buy-and-hold, 3/4 beat DCA, 1/4 beat the BTC-momentum regime control.
- 2024+ holdout beat buy-and-hold on 4/4 assets, but the evidence is thin: only 8 trades per asset.
- Concentration gate failed: 0/4 assets cleared the 20% top-PnL-block cap.
- Gold-volatility stress episodes are sparse and do not provide a deployable standalone crypto risk-off overlay after costs and benchmark comparison.

## Conclusion

- The GVZ gold-volatility risk-off overlay is not deployable as tested.
- This closes the simple GVZ z-score stress overlay; do not retest the same GVZ threshold/hysteresis rule without a fundamentally different mechanism or confirmation signal.
