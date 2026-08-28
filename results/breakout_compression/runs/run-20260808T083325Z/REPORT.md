# Breakout Compression Validation

**Verdict:** **REJECTED**

## Frozen hypothesis

Accepted breakouts that emerge from prior volatility compression may carry more persistent demand than the unfiltered acceptance parent.

## Exact rule

- Base parent: 50-bar acceptance long, 2-bar acceptance window, 0.1 ATR breakout buffer, 24-bar max hold, 2 ATR stop.
- Compression gate: ATR(14)/close percentile rank over the prior 252 completed 4h bars must be at or below the selected threshold.
- Compression is measured on `shift(1)` data, so the breakout bar itself never contributes to the filter.
- Selected threshold from development+validation only: **0.50**.
- Entries still occur at the next 4h open; no overlapping positions within an asset.

## Strategy summary

| variant | total_return | cagr | sharpe | sortino | maximum_drawdown | trades | win_rate | profit_factor | exposure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Compression-selected acceptance | 3.1181 | 0.1796 | 1.11181 | 0.677402 | 0.166864 | 385 | 0.350649 | 1.73276 | 0.0993925 |
| Unfiltered acceptance parent | 2.83303 | 0.169766 | 0.868816 | 0.571493 | 0.218675 | 542 | 0.346863 | 1.4612 | 0.139167 |
| Immediate breakout baseline | 3.96522 | 0.205634 | 0.957191 | 0.655802 | 0.213499 | 680 | 0.294118 | 1.49034 | 0.151744 |
| Doubled costs | 2.19345 | 0.145109 | 0.925892 | 0.56649 | 0.184435 | 385 | 0.342857 | 1.58772 | 0.0993392 |
| Entry delayed one extra bar | 2.25606 | 0.147707 | 0.946321 | 0.56862 | 0.170998 | 384 | 0.346354 | 1.60027 | 0.093921 |

## Partition summary

| partition | selected_total_return | selected_sharpe | selected_trades | parent_total_return | parent_sharpe | parent_trades | increment_vs_parent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| development_2018_2019 | 0.64553 | 1.25262 | 61 | 0.269371 | 0.5654 | 79 | 0.376159 |
| validation_2020_2023 | 1.48587 | 1.33074 | 193 | 1.71351 | 1.14835 | 285 | -0.227638 |
| forward_2024_2026 | 0.150039 | 0.461887 | 131 | 0.177193 | 0.452198 | 178 | -0.0271546 |

## Benchmark summary

| strategy | final_usd | final_units | total_return | cagr | maximum_drawdown | sharpe | benchmark_type |
| --- | --- | --- | --- | --- | --- | --- | --- |
| basket_buy_hold_btc_eth_sol | 110774 |  | 10.0774 | 0.323992 | 0.941472 | 0.810034 | basket_buy_hold |
| basket_daily_dca_btc_eth_sol | 38477.2 |  | 2.84772 | 0.170289 | 0.850128 | 1.70142 | basket_daily_dca |
| basket_weekly_dca_btc_eth_sol | 38197.1 |  | 2.81971 | 0.169291 | 0.848753 | 1.71547 | basket_weekly_dca |
| buy_hold_BTC | 46437.6 | 0.728366 | 3.64376 | 0.196254 | 0.814172 | 0.605529 | buy_hold |
| daily_dca_BTC | 40008.3 | 0.627524 | 3.00083 | 0.17563 | 0.750893 | 1.7786 | daily_dca |
| weekly_dca_BTC | 40004.5 | 0.627465 | 3.00045 | 0.175617 | 0.750676 | 1.78486 | weekly_dca |
| buy_hold_ETH | 25792.8 | 13.6287 | 1.57928 | 0.116919 | 0.940801 | 0.549123 | buy_hold |
| daily_dca_ETH | 34826.9 | 18.4023 | 2.48269 | 0.156754 | 0.808185 | 1.57718 | daily_dca |
| weekly_dca_ETH | 34761.5 | 18.3677 | 2.47615 | 0.156501 | 0.808067 | 1.59763 | weekly_dca |
| buy_hold_SOL | 260091 | 3505.27 | 25.0091 | 0.727673 | 0.965988 | 1.04544 | buy_hold |
| daily_dca_SOL | 40596.5 | 547.122 | 3.05965 | 0.265044 | 0.961855 | 1.80692 | daily_dca |
| weekly_dca_SOL | 39825.3 | 536.73 | 2.98253 | 0.26098 | 0.9616 | 1.79567 | weekly_dca |
| buy_hold_XRP | 21300.7 | 19980 | 1.13007 | 0.0962144 | 0.857975 | 0.488931 | buy_hold |
| daily_dca_XRP | 22430.3 | 21039.6 | 1.24303 | 0.103117 | 0.820846 | 1.51337 | daily_dca |
| weekly_dca_XRP | 22463.4 | 21070.7 | 1.24634 | 0.103315 | 0.820485 | 1.51989 | weekly_dca |

## Hostile checks

| check | selected_total_return | benchmark_total_return | difference | status |
| --- | --- | --- | --- | --- |
| Validation improvement vs unfiltered parent | 1.48587 | 1.71351 | -0.227638 | Fail |
| Forward improvement vs unfiltered parent | 0.150039 | 0.177193 | -0.0271546 | Fail |
| Full sample vs immediate breakout | 3.1181 | 3.96522 | -0.847112 | Fail |
| Doubled costs remain positive | 2.19345 | 0 | 2.19345 | Pass |
| One-extra-bar delay remains positive | 2.25606 | 0 | 2.25606 | Pass |
| Remove best asset (BTC) | 2.16785 | 0 | 2.16785 | Pass |
| Vs basket daily DCA | 3.1181 | 2.84772 | 0.270384 | Pass |
| Vs basket weekly DCA | 3.1181 | 2.81971 | 0.298393 | Pass |

## Verdict

**REJECTED** — The compression filter failed its primary preregistered gate: it did not improve validation return versus the unfiltered acceptance parent.

Artifacts: `strategy_summary.csv`, `partition_summary.csv`, `selection_grid.csv`, `sensitivity_checks.csv`, `hostile_checks.csv`, `benchmark_summary.csv`, `trades.csv`, `equity_curve.csv`, `config.json`.
