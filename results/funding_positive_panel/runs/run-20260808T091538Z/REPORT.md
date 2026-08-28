# Positive funding panel validation

Run artifact: `/Users/vr/Documents/Projects/validated-crypto-strategies/results/funding_positive_panel/runs/run-20260808T091538Z/REPORT.md`

## Key findings

- **Primary rule tested:** across the real Binance funding universe **BTC / ETH / SOL / XRP / BNB / ADA / DOGE / AVAX / LINK**, if one or more completed 8h funding prints are **>= +5 bps**, select the **single most positive** asset, enter **spot long at the next hourly open**, hold **8h**, then exit and wait **24h** before the next trade.
- **Capital rule:** one global reserve sleeve, non-overlapping trades, using only real Binance hourly spot bars and real Binance USD-M funding history.
- **Benchmarks:** same fixed **$10,000** reserve released as equal daily contributions, compared against **daily BTC, ETH, SOL, and XRP DCA** plus a **daily equal-weight nine-asset universe DCA**.

## Result table

| strategy | terminal_value | event_count | avg_trade_return | win_rate |
|---|---|---|---|---|
| cash_reserve | 10000 | 0 | nan | nan |
| daily_btc_dca | 15105.4 | 2034 | nan | nan |
| daily_eth_dca | 8602.24 | 2034 | nan | nan |
| daily_sol_dca | 19664.6 | 2034 | nan | nan |
| daily_xrp_dca | 15583.8 | 2034 | nan | nan |
| daily_equal_weight_universe_dca | 10757.1 | 2034 | nan | nan |
| weekly_equal_weight_universe_dca | 10647.4 | 291 | nan | nan |
| always_long_equal_weight_schedule | 9011.9 | 124 | 0.00290983 | 0.580645 |
| random_asset_schedule_baseline | 8221.13 | 124 | -0.000121006 | 0.443548 |
| positive_funding_persistence_panel | 9586.24 | 124 | 0.00520172 | 0.451613 |

## Honest conclusion

> **Rejected.** The positive-funding persistence rule finished at **$9586.24** across **124 trades**. The decisive benchmark gate remains the best required DCA baseline at **$19664.59**.

## Decisive hostile checks

| check | terminal_value | net_return | beats_primary |
|---|---|---|---|
| doubled_cost | 8929.23 | -0.107077 | False |
| exclude_best_trade | 9529.94 | -0.0470062 | False |
| random_baseline | 8221.13 | -0.177887 | False |

## Files

- `/Users/vr/Documents/Projects/validated-crypto-strategies/results/funding_positive_panel/runs/run-20260808T091538Z/strategy_summary.csv`
- `/Users/vr/Documents/Projects/validated-crypto-strategies/results/funding_positive_panel/runs/run-20260808T091538Z/trade_log.csv`
- `/Users/vr/Documents/Projects/validated-crypto-strategies/results/funding_positive_panel/runs/run-20260808T091538Z/equity_curves.csv`
- `/Users/vr/Documents/Projects/validated-crypto-strategies/results/funding_positive_panel/runs/run-20260808T091538Z/partition_summary.csv`
- `/Users/vr/Documents/Projects/validated-crypto-strategies/results/funding_positive_panel/runs/run-20260808T091538Z/signal_panel.csv`
- `/Users/vr/Documents/Projects/validated-crypto-strategies/results/funding_positive_panel/runs/run-20260808T091538Z/sensitivity_checks.csv`
- `/Users/vr/Documents/Projects/validated-crypto-strategies/results/funding_positive_panel/runs/run-20260808T091538Z/hostile_checks.csv`

## Manifest excerpt

```json
{
  "spec": {
    "name": "positive_funding_persistence_panel",
    "funding_threshold": 0.0005,
    "hold_hours": 8,
    "cooldown_hours": 24
  },
  "raw_signal_count": 124
}
```
