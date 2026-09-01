# Volume-spike capitulation flush rebound validation

Run artifact: `results/volume_flush_rebound/runs/run-20260901T191754Z/`

## Key findings

- **Primary rule tested:** on real Binance spot **1h** OHLCV for **BTC/ETH/SOL/XRP**, trigger when a bar's `low / prior_close - 1 <= -3.0%` (wick-sensitive single-bar drop) AND `volume / rolling_mean(volume.shift(1), 20) >= 3.0x` (abnormal volume, proxy for a forced-selling/liquidation-cascade flush since this repo has no real liquidation-print feed). Enter spot long at the **next bar's open**, hold **24h**, cooldown **24h** before the next entry.
- **Costs:** repo-standard 30bps round trip (15bps/side).
- **Benchmarks:** cash, buy-and-hold, daily DCA, a **no-volume-filter control** (identical -3% drop trigger, no volume requirement — isolates whether volume adds anything), and a **seeded random-timing control** matched on trade count/hold/cooldown.
- **Sample:** full available Binance 1h history through 2026-07-27 (BTC/ETH/XRP from 2018, SOL from 2020-08-11).

## Result table (relative equity, $1 start)

| Asset | Trades | Primary final | Doubled-cost | No-vol control | Random control | Buy-and-hold | DCA |
|---|---:|---:|---:|---:|---:|---:|---:|
| BTC | 203 | 0.51 | 0.28 | 0.39 | 0.51 | 4.71 | 3.999 |
| ETH | 301 | 0.05 | 0.02 | 0.06 | 0.13 | 2.60 | 3.481 |
| SOL | 267 | 1.81 | 0.81 | 93.93 | 0.74 | 25.14 | 4.058 |
| XRP | 306 | 0.50 | 0.20 | 1.86 | 2.84 | 1.16 | 2.242 |

## Honest conclusion

> **REJECTED, decisive.** 0/4 assets beat buy-and-hold or DCA; 3/4 assets (BTC/ETH/XRP) lose absolute capital outright on the primary rule. The no-volume-filter control strictly dominates the volume-filtered version on SOL and XRP (93.9x and 1.86x vs 1.81x and 0.50x) — the volume spike requirement is actively harmful, not additive, on this construction: it selects bars where the drop is deepest but the subsequent rebound is *not* durable enough to offset the drawdown taken on entry. The random-timing control also beats the primary rule on BTC and XRP, indicating the trigger carries no consistent directional value versus randomly-timed entries of the same size/frequency. Only 1 of 8 preregistered gates passed (real 2024-07+ holdout trades existed on all 4 assets, but that alone is not evidence of edge).

## Why the mechanism likely fails

- A 3%+ single-bar low-vs-prior-close drop with 3x volume is common in crypto (200-300 non-overlapping trigger events per asset over the full history) — this is closer to "any sharp selloff" than a genuine rare liquidation-cascade exhaustion event.
- Fixed 24h hold does not adapt to how long the flush actually needs to resolve; buying into an ongoing decline (rather than a confirmed reversal) repeatedly bought further weakness, consistent with the prior DVOL-fear-spike and FGI-contrarian rejections in this program.
- No price-reclaim confirmation was used (a plain trigger-and-hold design, matching this program's other now-rejected "buy the panic" mechanisms) — a reclaim-confirmed variant is a possible but low-priority follow-up given how decisively this rejected.

## Files

- `results/volume_flush_rebound/runs/run-20260901T191754Z/strategy_summary.csv`
- `results/volume_flush_rebound/runs/run-20260901T191754Z/partition_summary.csv`
- `results/volume_flush_rebound/runs/run-20260901T191754Z/{BTC,ETH,SOL,XRP}_trades.csv`
