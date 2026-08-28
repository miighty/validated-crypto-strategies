# Falling Fed-cut Odds → BTC Swing Validation

Run artifact: `/Users/vr/Documents/Projects/validated-crypto-strategies/results/fed_hawkish_btc/runs/run-20260808T082603Z/REPORT.md`

## Key findings

- **Primary rule tested:** across the real Polymarket **Fed-cut family** (March / May / June / September cut-deadline markets plus the `6+ cuts in 2024` market), if YES odds fall by at least **12 points over 24h** and remain at or below **45%**, enter **spot BTC long** at the **next hourly open**, hold **72h**, then exit and wait **24h** before the next entry.
- **Sample:** `2023-12-18` through the final overlapping Fed-market observation in the pinned repo, using only real Polymarket hourly YES odds plus real Binance BTC/ETH/SOL/XRP hourly spot candles.
- **Benchmarks:** same fixed **$10,000** reserve released as equal daily contributions, compared against **daily BTC, ETH, SOL, and XRP DCA**, plus **same-schedule always-long equal-weight** and **random-asset schedule** baselines.

## Result table

| strategy | terminal_value | event_count | avg_trade_return | win_rate | verdict |
|---|---|---|---|---|---|
| daily_btc_dca | 17123.4 | 367 | nan | nan | Baseline |
| daily_eth_dca | 13301.6 | 367 | nan | nan | Baseline |
| daily_sol_dca | 15184.8 | 367 | nan | nan | Baseline |
| daily_xrp_dca | 42097.1 | 367 | nan | nan | Baseline |
| always_long_equal_weight_schedule | 9932.39 | 9 | 0.00556044 | 0.555556 | Baseline |
| random_asset_schedule_baseline | 9789.84 | 9 | 0.00126084 | 0.555556 | Baseline |
| fed_hawkish_btc_swing | 10324.4 | 9 | 0.0173888 | 0.777778 | Inconclusive |

## Honest conclusion

> **Inconclusive.** The rule produced fewer than three holdout trades after 2024-06-01.

## Decisive hostile checks

| check | terminal_value | net_return | beats_primary |
|---|---|---|---|
| doubled_cost | 10236.1 | 0.0236087 | False |
| exclude_best_trade | 10106.8 | 0.0106797 | False |
| always_long_same_schedule | 9932.39 | -0.00676104 | False |
| random_asset_schedule | 9789.84 | -0.0210164 | False |

