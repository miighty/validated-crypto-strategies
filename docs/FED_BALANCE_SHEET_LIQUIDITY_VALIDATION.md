# Fed Balance-Sheet Liquidity Regime Validation

- **Experiment ID:** EXP-2026-09-06-FEDBALANCE-001
- **Verdict:** REJECTED
- **Primary rule:** Use real FRED `WALCL` (Federal Reserve total assets) as an external liquidity-cycle filter; long BTC/ETH/SOL/XRP only when the latest actionable WALCL print is above its prior-only 13-week SMA, else cash. Weekly macro observations are shifted one print before daily execution.
- **Why new:** First central-bank balance-sheet/liquidity-quantity signal in this repo; distinct from VIX, DXY, credit spreads, yield curve, and NFCI stress overlays.
- **Real data:** FRED WALCL cached at `data/macro_fed_balance_sheet/walcl_1w.csv.gz` (2003-03-19 to 2026-07-22); cached Binance spot daily OHLCV; no synthetic/proxy inputs.

## Results

| Asset | Risk-on days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1w action lag | 2024+ final vs B&H | Sharpe | MaxDD | Top block PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| BTC | 1196 (38.2%) | 5 | $31,136.74 | $46,344.78 | $39,941.66 | $84,689.49 | $14,589.22 | $30,673.17 | $26,096.51 | $7,727.98 vs $15,032.99 (2 trades) | 0.53 | -67.2% | 132.4% | Rejected |
| ETH | 1196 (38.2%) | 5 | $98,376.66 | $25,741.27 | $34,753.86 | $127,304.60 | $33,318.49 | $96,912.02 | $60,735.62 | $7,156.68 vs $8,268.92 (2 trades) | 0.76 | -75.5% | 125.7% | Rejected |
| SOL | 881 (40.5%) | 4 | $115,428.48 | $259,570.99 | $40,615.95 | $904,985.48 | $18,057.72 | $114,051.60 | $80,532.84 | $6,823.80 vs $7,272.68 (2 trades) | 0.90 | -90.7% | 165.9% | Rejected |
| XRP | 1196 (39.8%) | 5 | $13,506.11 | $21,258.13 | $22,385.07 | $37,077.30 | $29,940.79 | $13,305.03 | $7,400.88 | $6,467.04 vs $17,268.99 (2 trades) | 0.41 | -86.8% | 286.1% | Rejected |

## Decisive checks

- Benchmark gate failed: 1/4 beat buy-and-hold, 2/4 beat DCA, 0/4 beat the BTC-momentum regime control.
- 2024+ holdout gate failed: 0/4 beat buy-and-hold in the 2024+ partition.
- Concentration gate failed: 0/4 assets cleared the 20% top-PnL-block cap.
- WALCL's 13-week balance-sheet expansion state is too slow/coarse as a standalone crypto timing filter and adds no value over a trivial BTC-momentum regime control.

## Conclusion

- The Fed balance-sheet liquidity filter is not deployable as tested.
- This closes the simple WALCL-above-13-week-SMA construction; do not retest the same balance-sheet trend filter without a fundamentally different mechanism or confirmation rule.
