# Negative funding panel validation

Run artifact: `/Users/vr/Documents/Projects/validated-crypto-strategies/results/funding_negative_panel/runs/run-20260808T055210Z/REPORT.md`

## Key findings

- **Primary rule tested:** across the real Binance funding universe **BTC / ETH / SOL / XRP / BNB / ADA / DOGE / AVAX / LINK**, if one or more completed 8h funding prints are **<= -5 bps**, select the **single most negative** asset, enter **spot long at the next hourly open**, hold **24h**, then exit and wait **24h** before the next trade.
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
| always_long_equal_weight_schedule | 8243.12 | 113 | 0.00664246 | 0.513274 |
| random_asset_schedule_baseline | 7426.74 | 113 | -0.000499047 | 0.530973 |
| negative_funding_rebound_panel | 6747.34 | 113 | 0.00307773 | 0.451327 |

## Honest conclusion

> **Rejected.** The negative-funding rebound rule finished at **$6747.34** across **113 trades**, but the decisive benchmark gate is still negative because at least one required DCA benchmark finished higher (best required baseline: **$19664.59**).

## Decisive hostile checks

| check | terminal_value | net_return | beats_primary |
|---|---|---|---|
| doubled_cost | 6172.73 | -0.382727 | False |
| exclude_best_trade | 6731.44 | -0.326856 | False |
| random_baseline | 7426.74 | -0.257326 | True |

## Files

- `/Users/vr/Documents/Projects/validated-crypto-strategies/results/funding_negative_panel/runs/run-20260808T055210Z/strategy_summary.csv`
- `/Users/vr/Documents/Projects/validated-crypto-strategies/results/funding_negative_panel/runs/run-20260808T055210Z/trade_log.csv`
- `/Users/vr/Documents/Projects/validated-crypto-strategies/results/funding_negative_panel/runs/run-20260808T055210Z/equity_curves.csv`
- `/Users/vr/Documents/Projects/validated-crypto-strategies/results/funding_negative_panel/runs/run-20260808T055210Z/partition_summary.csv`
- `/Users/vr/Documents/Projects/validated-crypto-strategies/results/funding_negative_panel/runs/run-20260808T055210Z/signal_panel.csv`
- `/Users/vr/Documents/Projects/validated-crypto-strategies/results/funding_negative_panel/runs/run-20260808T055210Z/sensitivity_checks.csv`
- `/Users/vr/Documents/Projects/validated-crypto-strategies/results/funding_negative_panel/runs/run-20260808T055210Z/hostile_checks.csv`

## Manifest excerpt

```json
{
  "spec": {
    "name": "negative_funding_rebound_panel",
    "funding_threshold": -0.0005,
    "hold_hours": 24,
    "cooldown_hours": 24
  },
  "raw_signal_count": 113
}
```
