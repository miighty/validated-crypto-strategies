# MOVE Treasury-Rate-Volatility Risk-Off Overlay Validation

- **Experiment ID:** EXP-2026-09-09-MOVERISKOFF-001
- **Verdict:** REJECTED
- **Primary rule:** Use real Yahoo Finance ICE/BofA MOVE Index (`^MOVE`) daily closes as an external Treasury-rate-volatility stress overlay: if MOVE z-score >= +2.0 vs a prior-only 252-trading-day baseline, exit BTC/ETH/SOL/XRP at the next daily open; stay cash until z < +1.0, then re-enter at the next daily open.
- **Why new:** This tests bond/rates volatility specifically, distinct from already-rejected equity volatility (VIX/VXN), gold/oil volatility (GVZ/OVX), Treasury price trend (TLT), real yields, yield curve, credit spreads, equity-index trend, commodities, liquidity, FX, and crypto-native filters.
- **Real data:** Yahoo Finance `^MOVE` daily close cached at `data/macro_move/move_1d.csv.gz` (2003-11-25 to 2026-07-27); cached Binance spot daily OHLCV; no synthetic/proxy inputs.

## Results

| Asset | Risk-on days | Trades | Final | B&H | DCA | BTC momentum ctrl | Random regime | 2x cost | +1d action lag | 2024+ final vs B&H | Sharpe | MaxDD | Top block PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| BTC | 2650 (84.7%) | 16 | $89,437.78 | $46,344.78 | $39,941.66 | $84,689.49 | $27,325.75 | $85,246.15 | $81,015.03 | $11,397.32 vs $15,032.99 (4 trades) | 0.74 | -81.9% | 91.6% | Rejected |
| ETH | 2650 (84.7%) | 16 | $65,773.34 | $25,741.27 | $34,753.86 | $127,304.60 | $4,736.93 | $62,690.78 | $54,719.57 | $7,019.16 vs $8,268.92 (4 trades) | 0.67 | -94.5% | 223.7% | Rejected |
| SOL | 1869 (85.9%) | 11 | $493,770.97 | $259,570.99 | $40,615.95 | $904,985.48 | $115,077.54 | $477,742.37 | $451,424.16 | $4,452.18 vs $7,272.68 (4 trades) | 1.12 | -85.8% | 330.3% | Rejected |
| XRP | 2527 (84.0%) | 16 | $70,928.31 | $21,258.13 | $22,385.07 | $37,077.30 | $4,093.87 | $67,604.15 | $47,217.53 | $14,745.40 vs $17,268.99 (4 trades) | 0.62 | -74.7% | 173.1% | Rejected |

## Decisive checks

- Benchmark gate failed: 4/4 beat buy-and-hold, 4/4 beat DCA, and 2/4 beat the BTC-momentum regime control.
- 2024+ holdout gate: 0/4 beat their own buy-and-hold benchmark.
- Concentration gate failed: 0/4 assets cleared the 20% top-PnL-block cap.
- The MOVE stress state is a real external rates-volatility variable, but under this hysteresis rule it does not produce a deployable crypto risk-off overlay.

## Conclusion

- MOVE Treasury-rate-volatility stress does not produce a robust standalone crypto regime filter under this preregistered construction.
- Do not retest this same MOVE z-score/hysteresis overlay without a fundamentally different confirmation or sizing mechanism.
