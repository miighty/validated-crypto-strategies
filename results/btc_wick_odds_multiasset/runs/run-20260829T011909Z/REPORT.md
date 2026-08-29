# BTC/ETH/SOL/XRP wick + supportive odds multi-asset tightening pass

## Rule (identical to the frozen BTC-only primary rule; only the asset universe changed)

- Wick detector per asset: `low / rolling_max(high.shift(1), 48h) - 1 <= -10%`.
- Support filter: composite mean YES odds across BTC ETF / ETH ETF / Trump election / Bitcoin reserve markets, 24h delta >= -2 points.
- Confirmation: first close within 24h that is at least 3% above the event low.
- Entry: next hourly open after confirmation; exit 72h later.
- ONE shared non-overlapping capital sleeve across all 4 assets; cooldown 48h after each exit.

## Result table

                                     strategy  final_usd_value  final_cash_usd  final_anchor_equivalent  final_anchor_close  event_count  gross_spent_usd  total_costs_usd  total_return_on_committed_capital  max_drawdown avg_trade_return  win_rate
                                daily_btc_dca      9245.229236        0.000000                 0.145010            63755.86         1031     10000.000000        15.000000                          -0.075477      0.443181             <NA>      <NA>
                               weekly_btc_dca      9212.221661        0.000000                 0.144492            63755.86          148     10000.000000        15.000000                          -0.078778      0.442100             <NA>      <NA>
btc_only_replica_wick_supportive_odds_rebound     10846.028662    10846.028662                 0.170118            63755.86            6     19059.923136        57.179769                           0.084603      0.070057         0.048067       1.0
 btc_eth_sol_xrp_wick_supportive_odds_rebound      9854.099187     9854.099187                 0.154560            63755.86           23     47948.509200       143.845528                          -0.014590      0.246506         0.008309  0.478261

## Partition summary

              partition                     start                       end  final_usd_value  final_anchor_equivalent  events  costs_usd  max_drawdown  avg_trade_return                                      strategy
development_2023q4_2024 2023-10-01 00:00:00+00:00 2024-12-31 23:00:00+00:00      7642.782561                 0.081675       0   0.000000      0.273583               NaN                                 daily_btc_dca
    holdout_2025_onward 2025-01-01 00:00:00+00:00 2026-07-27 23:00:00+00:00      9245.229236                 0.145010       0   0.000000      0.443181               NaN                                 daily_btc_dca
development_2023q4_2024 2023-10-01 00:00:00+00:00 2024-12-31 23:00:00+00:00      7583.296200                 0.081039       0   0.000000      0.271127               NaN                         weekly_monday_btc_dca
    holdout_2025_onward 2025-01-01 00:00:00+00:00 2026-07-27 23:00:00+00:00      9212.221661                 0.144492       0   0.000000      0.442100               NaN                         weekly_monday_btc_dca
development_2023q4_2024 2023-10-01 00:00:00+00:00 2024-12-31 23:00:00+00:00      4828.301073                 0.051598       4  23.042829      0.070057          0.052214 btc_only_replica_wick_supportive_odds_rebound
    holdout_2025_onward 2025-01-01 00:00:00+00:00 2026-07-27 23:00:00+00:00     10846.028662                 0.170118       2  34.136941      0.067186          0.039774 btc_only_replica_wick_supportive_odds_rebound
development_2023q4_2024 2023-10-01 00:00:00+00:00 2024-12-31 23:00:00+00:00      4886.003495                 0.052214      20  96.562959      0.145204          0.014832  btc_eth_sol_xrp_wick_supportive_odds_rebound
    holdout_2025_onward 2025-01-01 00:00:00+00:00 2026-07-27 23:00:00+00:00      9854.099187                 0.154560       3  47.282568      0.246506         -0.035177  btc_eth_sol_xrp_wick_supportive_odds_rebound

## Hostile checks

               check  terminal_value beats_daily beats_weekly excluded_event_asset  excluded_event_timestamp
        doubled_cost    9.713335e+03        True         True                  NaN                       NaT
  exclude_best_event    9.651154e+03        True         True                  XRP 2025-04-10 02:00:00+00:00
best_event_pnl_share    2.029455e+11        <NA>         <NA>                  NaN                       NaT
per_asset_trades_BTC    1.131108e-01           1         <NA>                  NaN                       NaT
per_asset_trades_ETH   -1.828421e-02           6         <NA>                  NaN                       NaT
per_asset_trades_SOL    1.019023e-02           9         <NA>                  NaN                       NaT
per_asset_trades_XRP    1.371158e-02           7         <NA>                  NaN                       NaT

## Verdict

{
  "label": "promising_but_inconclusive",
  "reason": "Beats baselines and survives doubled cost, but either concentration or best-event exclusion still shows fragility.",
  "event_count": 23,
  "beats_both_dca": true,
  "doubled_cost_pass": true,
  "exclude_best_event_pass": true,
  "concentration_ok": false,
  "holdout_events": 3,
  "holdout_avg_trade_return": -0.03517737644362673
}

## Manifest

{
  "config": {
    "initial_capital": 10000.0,
    "one_way_cost": 0.0015,
    "contribution_hour_utc": 9,
    "sample_start": "2023-10-01T00:00:00Z",
    "holdout_start": "2025-01-01T00:00:00Z",
    "supportive_families": [
      "btc_etf",
      "eth_etf",
      "trump_election",
      "bitcoin_reserve"
    ],
    "assets": [
      "BTC",
      "ETH",
      "SOL",
      "XRP"
    ],
    "primary_rule": "Identical to the frozen BTC-only rule (wick_window=48h, drawdown<=-10%, support_delta_floor>=-2pts, bounce>=3% within 24h, hold=72h, cooldown=48h), applied independently to BTC/ETH/SOL/XRP 1h bars sharing ONE non-overlapping capital sleeve (earliest qualifying signal across assets wins; no other asset may enter until the open trade exits and the cooldown elapses)."
  },
  "raw_signal_counts_per_asset": {
    "BTC": 6,
    "ETH": 12,
    "SOL": 21,
    "XRP": 12
  },
  "sample_start": "2023-10-01T00:00:00+00:00",
  "sample_end": "2026-07-27T23:00:00+00:00"
}

