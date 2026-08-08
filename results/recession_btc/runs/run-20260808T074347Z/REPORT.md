# Recession Odds → BTC Relief Validation

Run artifact: `/Users/vr/Documents/Projects/validated-crypto-strategies/results/recession_btc/runs/run-20260808T074347Z/REPORT.md`

## Key findings

- **Primary rule tested:** when real Polymarket **US recession YES odds** fall by at least **5 points over 24h** and remain at or below **45%**, enter **spot BTC long** at the **next hourly open**, hold **72h**, then exit and wait **24h** before the next entry.
- **Sample:** `2025-09-30` through the pinned repo cutoff using only real Polymarket hourly YES odds plus real Binance BTC/ETH/SOL/XRP hourly spot candles.
- **Benchmarks:** same fixed **$10,000** reserve released as equal daily contributions, compared against **daily BTC, ETH, SOL, and XRP DCA**, plus **same-schedule always-long equal-weight** and **random-asset schedule** baselines.

## Result table

| strategy | terminal_value | event_count | avg_trade_return | win_rate | verdict |
|---|---|---|---|---|---|
| daily_btc_dca | 8122.2 | 301 | nan | nan | Baseline |
| daily_eth_dca | 7936.99 | 301 | nan | nan | Baseline |
| daily_sol_dca | 7408.1 | 301 | nan | nan | Baseline |
| daily_xrp_dca | 6849.14 | 301 | nan | nan | Baseline |
| always_long_equal_weight_schedule | 10203.6 | 15 | 0.00188103 | 0.533333 | Baseline |
| random_asset_schedule_baseline | 10275.8 | 15 | 0.00121095 | 0.466667 | Baseline |
| recession_relief_btc_swing | 10215.7 | 15 | 0.00241415 | 0.533333 | Rejected |

## Honest conclusion

> **Rejected.** A same-schedule baseline matched or beat the signal, so the odds filter added no value.

## Decisive hostile checks

| check | terminal_value | net_return | beats_primary |
|---|---|---|---|
| doubled_cost | 10086.6 | 0.00865956 | False |
| exclude_best_trade | 10213.7 | 0.021368 | False |
| always_long_same_schedule | 10203.6 | 0.0203576 | False |
| random_asset_schedule | 10275.8 | 0.027576 | True |

