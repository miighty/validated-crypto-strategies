# Moderate positive funding persistence validation

Run artifact: `/Users/vr/Documents/Projects/validated-crypto-strategies/results/funding_moderate_positive_persistence/runs/run-20260904T204855Z/REPORT.md`

## Key findings

- **Primary rule tested:** across real Binance funding for **BTC / ETH / SOL / XRP / BNB / ADA / DOGE / AVAX / LINK**, if one or more completed 8h funding prints land in the preregistered **+1 to +5 bps** bucket, select the **single most positive** asset below +5 bps, enter **spot long at the next hourly open**, hold **8h**, then exit and wait **24h** before the next trade.
- **Why this is genuinely new:** prior studies tested **negative funding mean reversion** (<= -5 bps) and **extreme positive funding persistence** (>= +5 bps). This run isolates the middle regime where crowded carry may still persist before becoming too crowded.
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
| always_long_equal_weight_schedule | 3097.88 | 1046 | -0.000519369 | 0.505736 |
| random_asset_schedule_baseline | 2906.77 | 1046 | -0.00125055 | 0.464627 |
| moderate_positive_funding_persistence_panel | 2728.86 | 1046 | -0.00125266 | 0.456979 |

## Bucket diagnostic

| asset | bucket | horizon_hours | sample_count | avg_gross_return | avg_net_return | holdout_count_2025_onward | holdout_avg_gross_return |
|---|---|---|---|---|---|---|---|
| ALL | le_-5bps | 8 | 281 | 0.00907193 | 0.00607193 | 13 | 4.02171e-05 |
| ALL | le_-5bps | 16 | 281 | 0.00903149 | 0.00603149 | 13 | -0.00303101 |
| ALL | le_-5bps | 24 | 281 | 0.0120965 | 0.00909646 | 13 | -0.00404252 |
| ALL | -5_to_-1bps | 8 | 1740 | 0.00099198 | -0.00200802 | 583 | 0.00121455 |
| ALL | -5_to_-1bps | 16 | 1740 | 0.00219015 | -0.000809851 | 583 | 0.00185093 |
| ALL | -5_to_-1bps | 24 | 1740 | 0.00359439 | 0.000594391 | 583 | 0.00199506 |
| ALL | -1_to_+1bps | 8 | 13486 | 0.000250518 | -0.00274948 | 5806 | -0.000270074 |
| ALL | -1_to_+1bps | 16 | 13478 | 0.000685112 | -0.00231489 | 5798 | -0.000206201 |
| ALL | -1_to_+1bps | 24 | 13478 | 0.00125926 | -0.00174074 | 5798 | -0.000333875 |
| ALL | +1_to_+5bps | 8 | 12558 | 0.00125559 | -0.00174441 | 1698 | -0.000577309 |
| ALL | +1_to_+5bps | 16 | 12557 | 0.00242875 | -0.000571251 | 1697 | -0.00131418 |
| ALL | +1_to_+5bps | 24 | 12557 | 0.0031054 | 0.000105403 | 1697 | -0.00100193 |
| ALL | ge_+5bps | 8 | 1230 | 0.00359488 | 0.000594879 | 0 | nan |
| ALL | ge_+5bps | 16 | 1230 | 0.00749917 | 0.00449917 | 0 | nan |
| ALL | ge_+5bps | 24 | 1230 | 0.0100343 | 0.00703425 | 0 | nan |

## Honest conclusion

> **Rejected.** The moderate-positive-funding panel finished at **$2728.86** across **1046 trades**. Best required baseline finished at **$19664.59**.
> Pooled +1 to +5 bps forward 8h return averaged **0.126% gross** and **-0.174% net** per event
> Zero-funding bucket averaged **0.025% gross** over the same 8h horizon.

## Decisive hostile checks

| check | terminal_value | net_return | beats_primary |
|---|---|---|---|
| doubled_cost | 1671.63 | -0.832837 | False |
| exclude_best_trade | 2723.22 | -0.727678 | False |
| random_baseline | 2906.77 | -0.709323 | True |

## Files

- `/Users/vr/Documents/Projects/validated-crypto-strategies/results/funding_moderate_positive_persistence/runs/run-20260904T204855Z/strategy_summary.csv`
- `/Users/vr/Documents/Projects/validated-crypto-strategies/results/funding_moderate_positive_persistence/runs/run-20260904T204855Z/trade_log.csv`
- `/Users/vr/Documents/Projects/validated-crypto-strategies/results/funding_moderate_positive_persistence/runs/run-20260904T204855Z/equity_curves.csv`
- `/Users/vr/Documents/Projects/validated-crypto-strategies/results/funding_moderate_positive_persistence/runs/run-20260904T204855Z/partition_summary.csv`
- `/Users/vr/Documents/Projects/validated-crypto-strategies/results/funding_moderate_positive_persistence/runs/run-20260904T204855Z/signal_panel.csv`
- `/Users/vr/Documents/Projects/validated-crypto-strategies/results/funding_moderate_positive_persistence/runs/run-20260904T204855Z/sensitivity_checks.csv`
- `/Users/vr/Documents/Projects/validated-crypto-strategies/results/funding_moderate_positive_persistence/runs/run-20260904T204855Z/hostile_checks.csv`
- `/Users/vr/Documents/Projects/validated-crypto-strategies/results/funding_moderate_positive_persistence/runs/run-20260904T204855Z/bucket_forward_returns.csv`

## Manifest excerpt

```json
{
  "spec": {
    "name": "moderate_positive_funding_persistence_panel",
    "min_funding_threshold": 0.0001,
    "max_funding_threshold": 0.0005,
    "hold_hours": 8,
    "cooldown_hours": 24
  },
  "raw_signal_count": 1046
}
```
