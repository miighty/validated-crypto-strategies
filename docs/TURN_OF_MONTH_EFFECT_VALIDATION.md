# Turn-of-Month Calendar Effect Validation

Run artifact: `results/turn_of_month_effect/runs/run-20260830T145401Z/`

## Key findings

- **Primary rule tested:** long only during the turn-of-month window (last 1 calendar day
  of the month through first 3 calendar days of the following month, ~4 days/month) on
  BTC/ETH/SOL/XRP; cash otherwise. Enter/exit at daily opens, 30bps round-trip cost.
- **Sample:** real Binance spot daily OHLCV, full available history per asset (BTC/ETH from
  2018-01-01, SOL from 2020-08-11, XRP from 2018-05-04) through 2026-07-27.
- **Mechanism:** month-end/month-start institutional and payroll-cycle capital flows
  (Ariel 1987 turn-of-month effect, well documented in TradFi equities) — genuinely new
  monthly-cycle mechanism, distinct from the already-rejected intra-week WEEKEND_EFFECT and
  US_SESSION_EFFECT calendar studies.

## Result table

| Asset | Rule final | B&H final | Doubled-cost final | Best-trade-excluded final | Beats B&H | Test partition |
|---|---:|---:|---:|---:|---|---|
| BTC | 1.42x | 4.77x | 1.04x | 1.18x | **No** | Loses |
| ETH | 3.44x | 2.51x | 2.53x | 2.65x | Yes | Loses |
| SOL | 3.20x | 22.50x | 2.59x | 2.26x | **No** | Loses |
| XRP | 1.07x | 1.20x | 0.80x | 0.77x | **No** | Loses (and fails best-trade exclusion) |

## Honest conclusion

**REJECTED.** Only 1 of 4 assets (ETH) beat continuous buy-and-hold on the full sample, and
that asset still lost to buy-and-hold in both the validation (2020-2024) and test (2024-2026)
partitions — the full-sample edge came entirely from the 2018-2020 development window, where
buy-and-hold itself was deeply negative (ETH -83%, BTC -46%) and any intermittent-exposure rule
looks good by comparison. No asset passed the test-partition check. XRP additionally failed the
best-trade-exclusion concentration check.

## Decisive blockers

1. **0 of 4 assets** beat buy-and-hold with costs on the full sample after also passing the
   test partition (ETH beat full-sample B&H but failed the test-partition gate).
2. **0 of 4 assets** survived doubled round-trip costs while beating B&H.
3. Apparent full-sample "wins" (ETH) are development-partition artifacts of the 2018-2020 bear
   market, not evidence of a real turn-of-month flow effect — buy-and-hold decisively wins in
   every partition after 2020 for every asset.

## Files

- `results/turn_of_month_effect/runs/run-20260830T145401Z/strategy_summary.csv`
- `results/turn_of_month_effect/runs/run-20260830T145401Z/partition_summary.csv`
- `results/turn_of_month_effect/runs/run-20260830T145401Z/{BTC,ETH,SOL,XRP}_tom_trades.csv`
- `results/turn_of_month_effect/runs/run-20260830T145401Z/verdict.txt`
