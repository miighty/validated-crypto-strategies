# Yield-Curve Inversion Risk-Off Overlay Validation

- **Experiment ID:** EXP-2026-09-06-YIELDCURVE-001
- **Verdict:** PROMISING BUT INCONCLUSIVE
- **Primary rule:** If real FRED 10-Year Treasury Constant Maturity minus real FRED 2-Year Treasury Constant Maturity (`DGS10 - DGS2`) z-score <= -2.0 vs a prior-only 252-trading-day baseline, exit BTC/ETH/SOL/XRP at the next daily open; stay cash until z > -1.0, then re-enter at the next daily open.
- **Why new:** First Treasury yield-curve term-spread signal in this repo; distinct from VIX volatility stress, DXY dollar trend, and BAA credit-spread stress.
- **Real data:** FRED DGS10 and DGS2 cached at `data/macro_credit/treasury_10y2y_spread_1d.csv.gz` (1977-06-02 to 2026-07-27); cached Binance spot daily OHLCV; no synthetic/proxy inputs.

## Results

| Asset | Risk-off days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1d action lag | 2024+ final vs B&H | Sharpe | MaxDD | Top block PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| BTC | 781 (25.0%) | 7 | $429,737.65 | $46,344.78 | $39,941.66 | $84,689.49 | $11,686.96 | $420,807.21 | $388,981.39 | $15,741.54 vs $15,032.99 (1 trades) | 1.07 | -61.8% | 57.5% | Inconclusive |
| ETH | 781 (25.0%) | 7 | $183,354.93 | $25,741.27 | $34,753.86 | $127,304.60 | $2,801.32 | $179,544.61 | $172,873.27 | $8,126.09 vs $8,268.92 (1 trades) | 0.84 | -76.9% | 70.8% | Inconclusive |
| SOL | 460 (21.1%) | 4 | $3,622,033.45 | $259,570.99 | $40,615.95 | $904,985.48 | $331,926.44 | $3,578,828.57 | $3,260,689.19 | $7,275.62 vs $7,272.68 (1 trades) | 1.44 | -74.7% | 68.9% | Inconclusive |
| XRP | 730 (24.3%) | 6 | $58,627.26 | $21,258.13 | $22,385.07 | $37,077.30 | $41,283.17 | $57,581.40 | $54,946.84 | $19,629.08 vs $17,268.99 (1 trades) | 0.67 | -71.2% | 52.2% | Inconclusive |

## Decisive checks

- Benchmark gate passed on headline capital: 4/4 beat buy-and-hold, 4/4 beat DCA, 4/4 beat the BTC-momentum regime control.
- Concentration gate failed: 0/4 assets cleared the 20% top-PnL-block cap; observed top-block shares are 52%-71%.
- Test partition evidence is too sparse: 3/4 assets beat their own 2024+ buy-and-hold benchmark, but each asset has only one 2024+ exposure block.
- The result is not deployable as validated edge: the apparent macro-cycle timing win is driven by very few long regime blocks, not many independent trades.

## Conclusion

- Treasury 10y-2y curve flattening/inversion produced the strongest macro-overlay headline benchmark result so far, but it remains promising rather than accepted because concentration and independent-sample-count gates fail.
- A valid follow-up would need a preregistered tightening that increases independent evidence or caps block concentration without selecting trades after the fact.
