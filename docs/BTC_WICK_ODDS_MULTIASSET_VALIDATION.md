# BTC wick + supportive odds: multi-asset tightening pass (REJECTED)

Follow-up to the "promising but inconclusive" BTC-only finding in
`docs/BTC_WICK_ODDS_VALIDATION.md`. Per the near-miss refinement rule, the
identical preregistered rule (nothing retuned) was extended from BTC-only to
BTC/ETH/SOL/XRP sharing one non-overlapping capital sleeve, to see if more
real Binance 1h wick events + real Polymarket composite odds would resolve
the small-sample ambiguity.

Run artifact: `results/btc_wick_odds_multiasset/runs/run-20260829T011948Z/REPORT.md`

## Rule (unchanged from the frozen BTC-only primary)

- Wick detector per asset: `low / rolling_max(high.shift(1), 48h) - 1 <= -10%`.
- Support filter: composite mean YES odds across BTC ETF / ETH ETF / Trump election / Bitcoin reserve markets, 24h delta >= -2 points.
- Confirmation: first close within 24h that is at least 3% above the event low.
- Entry: next hourly open after confirmation; exit 72h later.
- ONE shared non-overlapping capital sleeve across all 4 assets (earliest qualifying signal wins); cooldown 48h after each exit.
- Sample: `2023-10-01` through `2026-07-27`, real Binance BTC/ETH/SOL/XRP hourly spot + real Polymarket hourly odds.

## Engine sanity check

The generalized multi-asset engine was first run BTC-only (`btc_only_replica_wick_supportive_odds_rebound`) and reproduced the original finding almost exactly: **$10,846.03** final value, 6 trades, 100% win rate — matching the original single-asset study. This confirms the extension is a faithful generalization, not a re-implementation bug.

## Result table

| Strategy | Final USD | Trades | Win rate | Total return on capital |
|---|---:|---:|---:|---:|
| Daily BTC DCA | 9245.23 | 1031 | n/a | -7.55% |
| Weekly BTC DCA | 9212.22 | 148 | n/a | -7.88% |
| BTC-only replica (sanity check) | 10846.03 | 6 | 100% | +8.46% |
| **BTC+ETH+SOL+XRP pooled sleeve** | **9854.10** | **23** | **47.8%** | **-1.46%** |

## Honest conclusion

> **REJECTED.** Pooling ETH/SOL/XRP wick events into the same capital sleeve raised the trade count from 6 to 23 but flipped the strategy from a genuine BTC-only edge (+8.46%) to a **net loss on committed capital (-1.46%)**. It still nominally "beat" both DCA baselines only because BTC DCA itself lost money in this bearish sample window — beating a losing benchmark is not evidence of edge. Per-asset breakdown shows the BTC-only signal (1 trade, +11.3% avg) is the entire source of quality; ETH (6 trades, -1.8% avg), SOL (9 trades, +1.0% avg), and XRP (7 trades, +1.4% avg) diluted it. Concentration also failed (best single event's PnL share undefined/too large relative to a near-zero net). Holdout (2025+) averaged -3.5% per trade across 3 trades.

**Verdict for the original BTC-only rule is unchanged**: still promising-but-inconclusive on BTC alone, but the wick pattern does *not* generalize to ETH/SOL/XRP under identical parameters — the BTC-specific supportive-odds gate does not transfer to noisier, higher-beta alts on the same 10%/3%/72h grid. Do not retune per-asset thresholds after seeing this result; if pursued further, per-asset parameters would need a fresh preregistration and fresh out-of-sample window.

## Files

- `results/btc_wick_odds_multiasset/runs/run-20260829T011948Z/REPORT.md`
- `results/btc_wick_odds_multiasset/runs/run-20260829T011948Z/strategy_summary.csv`
- `results/btc_wick_odds_multiasset/runs/run-20260829T011948Z/trade_log.csv`
- `results/btc_wick_odds_multiasset/runs/run-20260829T011948Z/partition_summary.csv`
- `results/btc_wick_odds_multiasset/runs/run-20260829T011948Z/hostile_checks.csv`
