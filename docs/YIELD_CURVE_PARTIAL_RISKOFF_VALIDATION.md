# Yield-Curve Partial Risk-Off Overlay Validation

- **Experiment ID:** EXP-2026-09-06-YIELDCURVE-PARTIAL-001
- **Verdict:** PROMISING BUT INCONCLUSIVE (tightening failed concentration gate)
- **Primary rule:** fixed exposure ladder using real FRED `DGS10-DGS2` z-score vs a prior-only 252-trading-day baseline: z <= -2.0 -> 0% long at next daily open; -2.0 < z <= -1.0 -> 50% long; z > -1.0 -> 100% long.
- **Why new:** preregistered concentration-tightening follow-up to the binary yield-curve risk-off overlay; it caps exposure during borderline flattening/inversion states without selecting trades after the fact.
- **Real data:** FRED DGS10 and DGS2 cached at `data/macro_credit/treasury_10y2y_spread_1d.csv.gz` (1977-06-02 to 2026-07-27); cached Binance spot daily OHLCV; no synthetic/proxy inputs.

## Results

| Asset | 0% days | 50% days | Blocks | Final | B&H | DCA | BTC momentum ctrl | Random ctrl | 2x cost | +1d action lag | 2024+ final vs B&H | Sharpe | MaxDD | Top block PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| BTC | 193 | 898 | 92 | $161,918.11 | $46,344.78 | $39,941.66 | $84,816.71 | $105,515.45 | $150,134.98 | $168,757.34 | $17,978.00 vs $15,032.99 (18 blocks) | 0.87 | -56.9% | 55.5% | Inconclusive |
| ETH | 193 | 898 | 92 | $90,752.12 | $25,741.27 | $34,753.86 | $127,495.85 | $23,545.17 | $83,884.16 | $101,018.61 | $9,383.71 vs $8,268.92 (18 blocks) | 0.72 | -75.0% | 167.7% | Inconclusive |
| SOL | 140 | 465 | 40 | $1,065,205.61 | $259,570.99 | $40,615.95 | $906,345.00 | $204,749.65 | $1,025,630.58 | $994,765.14 | $8,463.77 vs $7,272.68 (18 blocks) | 1.24 | -81.3% | 74.2% | Inconclusive |
| XRP | 186 | 803 | 81 | $61,501.77 | $21,258.13 | $22,385.07 | $37,133.00 | $33,259.29 | $57,366.17 | $70,391.07 | $21,518.82 vs $17,268.99 (18 blocks) | 0.63 | -71.2% | 60.8% | Inconclusive |

## Decisive checks

- Benchmark gate: 4/4 beat buy-and-hold, 4/4 beat DCA, 3/4 beat the BTC-momentum regime control.
- Concentration gate still failed: 0/4 assets cleared the 20% top-PnL-block cap.
- 2024+ partition remains thin/weak: 4/4 beat buy-and-hold, with only a few exposure-state blocks in the holdout.
- The partial ladder reduced the binary rule's headline convexity instead of validating it; the original edge remains a few-regime-block macro-cycle artifact, not a deployable repeated edge.

## Conclusion

- Promising but inconclusive: the honest concentration-tightening follow-up does not rescue the yield-curve overlay for deployment.
- Do not retest Treasury term-spread threshold ladders again without a fundamentally different data source or mechanism; simple z-score exposure timing remains a sparse macro-cycle effect, not a validated repeated edge.
