# BTC Shock -> Alt Underreaction Validation

## Primary rule

- If BTC rises at least 3% close-to-close over the prior 4 completed hourly bars and the target alt gained at most 60% of that BTC move over the same completed 4-hour window, deploy the full accrued reserve long the alt at the next hourly open, hold 72 hours, then return to cash.
- Costs: 0.15% per side.
- Sample: 2021-01-01T00:00:00Z through pinned Binance cutoff.

## Best strategy row

- Asset: XRP
- Terminal value: $22597.97
- Net return: 125.98%
- Trades: 106
- Verdict: Rejected

## Strategy table

asset  trade_count  terminal_value  net_return  verdict
  ETH           54    11995.175775    0.199518 Rejected
  SOL           66    10696.825317    0.069683 Rejected
  XRP          106    22597.965458    1.259797 Rejected

## Strongest passive DCA comparators

asset       strategy  terminal_value  net_return
  SOL  daily_sol_dca    19664.587722    0.966459
  SOL weekly_sol_dca    19022.668489    0.902267
  XRP  daily_xrp_dca    15583.786047    0.558379
  XRP weekly_xrp_dca    15557.178069    0.555718

## Hostile checks

asset                        check  trade_count  mean_trade_return
  ETH btc_shock_without_lag_filter          172           0.013841
  ETH          same_asset_momentum          246           0.002731
  ETH               matched_random            3          -0.005784
  SOL btc_shock_without_lag_filter          172           0.027542
  SOL          same_asset_momentum          330           0.017572
  SOL               matched_random            3          -0.015255
  XRP               matched_random            3           0.015639
  XRP          same_asset_momentum          262           0.013962
  XRP btc_shock_without_lag_filter          172           0.011667

No result is trading advice. This report uses only finalized Binance spot candles and predeclared execution timing.
