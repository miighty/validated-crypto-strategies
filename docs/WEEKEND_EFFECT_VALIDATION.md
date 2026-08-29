# Crypto weekend liquidity-withdrawal effect validation

Run artifact: `results/weekend_effect/runs/run-20260829T201148Z/`

## Hypothesis (frozen before results seen)

Crypto trades 24/7, but ETF authorized participants, CME futures desks,
options market-makers and other TradFi-linked liquidity providers are
largely absent on weekends. A rule that goes flat (cash) from Saturday
00:00 UTC through Monday 00:00 UTC and stays long the rest of the week
should beat continuous buy-and-hold after realistic round-trip costs,
because the "removed" weekend segment should contribute disproportionately
little (or negative) return relative to its risk.

## Design

- Universe: BTC, ETH, SOL, XRP, real Binance spot 1h OHLCV
  (`data/raw/*_1h.csv.gz`), full available history through 2026-07-27.
- Weekday-only rule: exit full position at Saturday 00:00 UTC open, re-enter
  at Monday 00:00 UTC open. Pure calendar rule, no lookahead.
- Weekend-only rule (mirror control): long only Sat 00:00 -> Mon 00:00 UTC.
- Costs: repo-standard 30bps round trip (15bps/side), charged on every
  weekly exit+re-entry (~104 trades/asset over the full sample).
- Partitions: development (2018-2020), validation (2020-2024), test
  (2024-2026), matching repo convention.
- Preregistered falsification: weekday-only rule must beat continuous
  buy-and-hold after costs on **all four assets**, survive doubled costs,
  and not lose to buy-and-hold in the test partition on any asset. Any
  single failure -> REJECTED.

## Result table

| Asset | Weekday-only final | Weekend-only final | Buy-and-hold final | Weekday beats B&H? |
|---|---:|---:|---:|---|
| BTC | 0.75x | 0.42x | 4.71x | No |
| ETH | 0.11x | 1.63x | 2.60x | No |
| SOL | 0.85x | 4.75x | 25.14x | No |
| XRP | 0.37x | 0.44x | 1.16x | No |

(Final values normalized to starting capital = 1.0x.)

## Honest conclusion

**REJECTED — decisively, on every asset and every partition.**

- The weekday-only rule lost to continuous buy-and-hold on **all 4 assets**,
  in **all 3 partitions** (development, validation, test), with no
  exceptions.
- Round-trip costs compound badly: ~104-448 exit/re-entry pairs over the
  full sample at 30bps round trip each drags 15-135%+ of terminal value
  depending on trade count, before any consideration of whether the
  weekend segment itself was actually weak.
- The mechanism itself does not hold up: weekend-only exposure was **not**
  uniformly weak. ETH and SOL weekend-only legs actually outperformed BTC's
  and XRP's weekday-only legs outright (ETH weekend +63% vs weekday -89%;
  SOL weekend +375% vs weekday -18%), meaning weekend price action is not
  reliably lower-quality than weekday price action across this universe.
  Any weekend "underperformance" story that exists for one asset in one
  window does not generalize.
- No hostile check was needed beyond the primary comparison — the rule
  failed the first and most basic gate (beat buy-and-hold after costs) on
  every single asset/partition combination, so doubled-cost and holdout
  checks are moot confirmations of the same conclusion.

## Files

- `results/weekend_effect/runs/run-20260829T201148Z/strategy_summary.csv`
- `results/weekend_effect/runs/run-20260829T201148Z/partition_summary.csv`
- `results/weekend_effect/runs/run-20260829T201148Z/{BTC,ETH,SOL,XRP}_weekday_trades.csv`
- `scripts/weekend_effect_validation.py`
