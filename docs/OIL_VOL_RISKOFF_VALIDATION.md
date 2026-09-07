# Oil-Implied-Volatility Risk-Off Validation

- **Experiment ID:** EXP-2026-09-07-OILVOLRISKOFF-001
- **Verdict:** REJECTED
- **Primary rule:** Use real FRED `OVXCLS` CBOE Crude Oil ETF Volatility Index as an external commodity/energy-stress overlay; if z-score >= +2.0 versus a prior-only 252-trading-day baseline, exit BTC/ETH/SOL/XRP at the next daily open; stay cash until z < +1.0, then re-enter at the next daily open.
- **Why new:** First oil-implied-volatility / energy-stress signal in this repo; distinct from VIX, GVZ/gold vol, DVOL, DXY, real yields, breakevens, credit spreads, Fed liquidity, M2, NFCI/STLFSI, and Treasury yield-curve signals.
- **Real data:** FRED OVXCLS cached at `data/macro_oil_vol/ovxcls_1d.csv.gz` (2008-05-09 to 2026-07-27); cached Binance spot daily OHLCV; no synthetic/proxy inputs.

## Results

| Asset | Risk-off days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1d action lag | 2024+ final vs B&H | Sharpe | Sortino | MaxDD | Top block PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- |
| BTC | 389 (12.4%) | 11 | $51,941.94 | $46,344.78 | $39,941.66 | $84,689.49 | $41,875.66 | $50,255.82 | $51,495.78 | $8,093.79 vs $15,032.99 (7 trades) | 0.63 | 0.92 | -72.4% | 147.9% | Rejected |
| ETH | 389 (12.4%) | 11 | $28,932.09 | $25,741.27 | $34,753.86 | $127,304.60 | $26,325.87 | $27,992.90 | $27,591.46 | $5,338.78 vs $8,268.92 (7 trades) | 0.54 | 0.79 | -87.7% | 529.9% | Rejected |
| SOL | 246 (11.3%) | 9 | $123,742.60 | $259,570.99 | $40,615.95 | $904,985.48 | $520,046.06 | $120,446.23 | $159,870.05 | $3,718.70 vs $7,272.68 (7 trades) | 0.91 | 1.44 | -96.5% | 608.5% | Rejected |
| XRP | 389 (12.9%) | 11 | $25,112.39 | $21,258.13 | $22,385.07 | $37,077.30 | $127,577.54 | $24,297.21 | $30,442.79 | $13,141.62 vs $17,268.99 (7 trades) | 0.50 | 0.84 | -83.1% | 193.2% | Rejected |

## Decisive checks

- Benchmark gate failed: 3/4 beat buy-and-hold, 3/4 beat DCA, 0/4 beat the BTC-momentum regime control.
- 2024+ holdout gate failed: 0/4 beat buy-and-hold in the 2024+ partition.
- Concentration gate failed: 0/4 assets cleared the 20% top-PnL-block cap.
- Oil-volatility stress episodes are sparse and do not provide a deployable standalone crypto risk-off overlay after costs and benchmark comparison.

## Conclusion

- The OVX oil-volatility risk-off overlay is not deployable as tested.
- This closes the simple OVX z-score stress overlay; do not retest the same OVX threshold/hysteresis rule without a fundamentally different mechanism or confirmation signal.
