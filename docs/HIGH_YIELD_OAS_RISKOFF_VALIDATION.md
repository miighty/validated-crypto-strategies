# High-Yield OAS Risk-Off Overlay Validation

- **Experiment ID:** EXP-2026-09-07-HYOASRISKOFF-001
- **Verdict:** REJECTED
- **Primary rule:** If real FRED ICE BofA US High Yield Index Option-Adjusted Spread (`BAMLH0A0HYM2`) z-score >= +2.0 vs a prior-only 252-trading-day baseline, exit BTC/ETH/SOL/XRP at the next daily open; stay cash until z < +1.0, then re-enter at the next daily open.
- **Why new:** First below-investment-grade OAS stress signal in this repo; distinct from investment-grade BAA-minus-Treasury spreads, VIX, DXY, real yields, breakevens, M2, WALCL, NFCI, and Treasury yield-curve signals.
- **Real data:** FRED BAMLH0A0HYM2 cached at `data/macro_credit/high_yield_oas_1d.csv.gz` (2024-08-21 to 2026-07-27 after the 252-day prior-only warmup; raw FRED graph export currently provides 2023-09-05 onward); cached Binance spot daily OHLCV; no synthetic/proxy inputs.

## Results

| Asset | Risk-off days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1d action lag | 2024+ final vs B&H | Sharpe | MaxDD | Top block PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| BTC | 42 (5.9%) | 2 | $8,624.25 | $10,771.19 | $7,531.20 | $10,716.11 | $9,819.56 | $8,572.66 | $8,784.60 | $8,624.25 vs $10,771.19 (2 trades) | -0.01 | -55.8% | 286.9% | Rejected |
| ETH | 42 (5.9%) | 2 | $5,339.81 | $7,333.85 | $7,373.13 | $12,115.38 | $7,309.83 | $5,307.87 | $5,197.95 | $5,339.81 vs $7,333.85 (2 trades) | -0.20 | -71.5% | -37.0% | Rejected |
| SOL | 42 (5.9%) | 2 | $3,705.62 | $5,199.81 | $5,683.46 | $4,744.80 | $4,831.77 | $3,683.45 | $3,574.09 | $3,705.62 vs $5,199.81 (2 trades) | -0.32 | -83.1% | -20.2% | Rejected |
| XRP | 42 (5.9%) | 2 | $14,663.36 | $17,903.09 | $7,272.46 | $14,673.56 | $20,210.52 | $14,575.64 | $14,780.33 | $14,663.36 vs $17,903.09 (2 trades) | 0.63 | -74.1% | 538.1% | Rejected |

## Decisive checks

- Benchmark gate failed: 0/4 beat buy-and-hold, 2/4 beat DCA, 0/4 beat the BTC-momentum regime control.
- Concentration gate failed: 0/4 assets cleared the 20% top-PnL-block cap.
- Test partition gate failed: 0/4 assets beat their own 2024+ buy-and-hold benchmark.
- High-yield OAS stress is a stale/lagging de-risking overlay for crypto in this construction: it removes exposure during broad stress but misses too much of the subsequent recovery.

## Conclusion

- High-yield OAS stress does not add deployable standalone timing value against simple crypto baselines.
- This rejects the simplest below-investment-grade credit-risk-off overlay; do not retest the same z>=2 / z<1 hysteresis construction without a fundamentally different sizing or confirmation rule.
