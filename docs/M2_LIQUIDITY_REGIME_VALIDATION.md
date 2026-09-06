# M2 Money-Supply Liquidity Regime Validation

- **Experiment ID:** EXP-2026-09-06-M2LIQUIDITY-001
- **Verdict:** REJECTED
- **Primary rule:** Use real FRED `M2SL` as an external broad-liquidity filter; long BTC/ETH/SOL/XRP only when the latest actionable monthly M2 YoY growth is positive and above its own prior-only 12-month average, otherwise cash. Monthly observations are shifted one full print before daily execution.
- **Why new:** First broad-money-supply signal in this repo; distinct from Fed balance-sheet assets (`WALCL`), stablecoin supply, DXY, VIX, credit spreads, Treasury yield curve, and NFCI.
- **Real data:** FRED M2SL cached at `data/macro_m2_liquidity/m2sl_1mo.csv.gz` (1961-01-01 to 2026-07-01); cached Binance spot daily OHLCV; no synthetic/proxy inputs.

## Results

| Asset | Risk-on days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1mo action lag | 2024+ final vs B&H | Sharpe | Sortino | MaxDD | Top block PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- |
| BTC | 1668 (53.3%) | 2 | $149,378.75 | $46,344.78 | $39,941.66 | $84,689.49 | $18,787.14 | $148,485.16 | $102,020.27 | $8,917.63 vs $15,032.99 (1 trades) | 0.93 | 1.40 | -63.3% | 113.0% | Rejected |
| ETH | 1668 (53.3%) | 2 | $134,380.63 | $25,741.27 | $34,753.86 | $127,304.60 | $18,957.18 | $133,576.76 | $124,818.19 | $5,176.16 vs $8,268.92 (1 trades) | 0.81 | 1.21 | -68.2% | 200.7% | Rejected |
| SOL | 1111 (51.0%) | 2 | $54,693.68 | $259,570.99 | $40,615.95 | $904,985.48 | $10,111.00 | $54,366.50 | $66,880.83 | $3,654.12 vs $7,272.68 (1 trades) | 0.71 | 1.19 | -76.3% | 312.5% | Rejected |
| XRP | 1668 (55.5%) | 2 | $87,093.41 | $21,258.13 | $22,385.07 | $37,077.30 | $44,207.32 | $86,572.41 | $70,206.02 | $16,892.98 vs $17,268.99 (1 trades) | 0.71 | 1.21 | -71.6% | 53.9% | Rejected |

## Decisive checks

- Benchmark gate failed: 3/4 beat buy-and-hold, 4/4 beat DCA, 3/4 beat the BTC-momentum regime control.
- 2024+ holdout gate failed: 0/4 beat buy-and-hold in the 2024+ partition.
- Concentration gate failed: 0/4 assets cleared the 20% top-PnL-block cap.
- M2's monthly broad-liquidity acceleration state is too slow/coarse as a standalone crypto timing filter and adds no value over a trivial BTC-momentum regime control.

## Conclusion

- The M2 money-supply liquidity filter is not deployable as tested.
- This closes the simple M2-YoY-acceleration construction; do not retest the same broad-money trend filter without a fundamentally different mechanism or confirmation rule.
