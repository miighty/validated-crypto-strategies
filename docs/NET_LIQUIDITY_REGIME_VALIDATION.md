# Fed Net-Liquidity Regime Validation

- **Experiment ID:** EXP-2026-09-07-NETLIQUIDITY-001
- **Verdict:** REJECTED
- **Primary rule:** Build real Fed net liquidity as `WALCL - WTREGEN - RRPONTSYD` in USD billions. Long BTC/ETH/SOL/XRP only when net liquidity is above its prior-only 91-day SMA and its prior-only 28-day change is positive; otherwise cash. Signal is shifted one day before execution.
- **Why new:** First combined Fed net-liquidity construction in this repo; distinct from the rejected raw WALCL balance-sheet trend, M2, DXY, real-yield, breakeven, credit-spread, VIX, NFCI, and Treasury-curve overlays.
- **Real data:** FRED WALCL/WTREGEN/RRPONTSYD cached at `data/macro_net_liquidity/net_liquidity_1d.csv.gz` (2008-12-05 to 2026-07-27); cached Binance spot daily OHLCV; no synthetic/proxy inputs.

## Results

| Asset | Risk-on days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +2d action lag | 2024+ final vs B&H | Sharpe | MaxDD | Top block PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| BTC | 1159 (37.0%) | 85 | $148,396.71 | $46,344.78 | $39,941.66 | $84,689.49 | $37,226.45 | $114,994.91 | $118,831.96 | $16,999.87 vs $15,032.99 (33 trades) | 0.99 | -64.5% | 21.9% | Rejected |
| ETH | 1159 (37.0%) | 85 | $76,997.18 | $25,741.27 | $34,753.86 | $127,304.60 | $47,112.44 | $59,666.31 | $88,799.51 | $11,282.27 vs $8,268.92 (33 trades) | 0.73 | -74.1% | 20.3% | Rejected |
| SOL | 865 (39.7%) | 72 | $549,961.85 | $259,570.99 | $40,615.95 | $904,985.48 | $115,230.84 | $443,123.17 | $702,368.28 | $14,629.39 vs $7,272.68 (33 trades) | 1.24 | -61.6% | 32.2% | Rejected |
| XRP | 1136 (37.8%) | 80 | $30,566.79 | $21,258.13 | $22,385.07 | $37,077.30 | $12,346.92 | $24,044.66 | $17,124.22 | $14,763.07 vs $17,268.99 (33 trades) | 0.52 | -69.5% | 69.8% | Rejected |

## Decisive checks

- Buy-and-hold/DCA gate passed on the full sample: 4/4 beat buy-and-hold and 4/4 beat DCA.
- Momentum benchmark gate failed: only 1/4 beat the BTC-momentum regime control.
- 2024+ holdout was mixed: 3/4 beat buy-and-hold in the 2024+ partition, but XRP failed.
- Concentration gate failed: 0/4 assets cleared the 20% top-PnL-block cap.
- Net liquidity improved some full-sample headline totals versus raw WALCL, but the edge remains sparse, concentration-dominated, and inferior to trivial BTC momentum.

## Conclusion

- The Fed net-liquidity filter is not deployable as tested.
- This closes the simple `WALCL - TGA - RRP` trend/acceleration construction; do not retest it without a fundamentally different confirmation or sizing rule.
