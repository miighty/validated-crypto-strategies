# US Session Return-Concentration Effect Validation

Run: `results/us_session_effect/runs/run-20260829T231553Z/`

## Hypothesis (preregistered)

Crypto trades 24/7, but the participants most likely to move price on
persistent directional information (US spot-ETF APs, CME desks, US options
market-makers) are concentrated during US cash-equity hours. A rule long
only during the US session window [13:00, 21:00) UTC and flat the rest of
each day should beat continuous buy-and-hold after costs.

This is mechanistically distinct from the already-REJECTED
[weekend liquidity-withdrawal effect](WEEKEND_EFFECT_VALIDATION.md), which
tested weekday-vs-weekend calendar days, not intraday session timing.

## Design

- Universe: BTC, ETH, SOL, XRP, real Binance spot 1h OHLCV (`data/raw/*_1h.csv.gz`).
- Primary rule: long [13:00, 21:00) UTC daily, cash otherwise. Enter at 13:00 UTC
  open, exit at 21:00 UTC open.
- Secondary/mirror control: long the complementary [21:00, 13:00) UTC window.
- Costs: repo-standard 30bps round trip (15bps/side).
- Partitions: development 2018-2020, validation 2020-2024, test 2024-2026.
- Falsification: primary rule must beat buy-and-hold on all 4 assets, survive
  doubled costs, and not lose in the test partition. Any failure -> REJECTED.

## Result

| Asset | Session final ($1 start) | B&H final | Trades | Session beats B&H |
| --- | ---: | ---: | ---: | --- |
| BTC | 0.000156 | 4.71 | 3,129 | No |
| ETH | 0.000068 | 2.60 | 3,129 | No |
| SOL | 0.001202 | 25.14 | 2,177 | No |
| XRP | 0.002075 | 1.16 | 3,007 | No |

All 4 assets, all 3 partitions: session rule loses to buy-and-hold, decisively.

## Honest conclusion

**REJECTED.** The rule enters/exits roughly once per day for the full
multi-year window (~3,000-3,129 trades per asset). At 30bps round-trip cost,
that is **~9.4x initial capital consumed by costs alone** (3,129 × 0.3% ≈
939%), independent of whether the US-session-return mechanism has any real
signal. This is a textbook case of the skill's "high-frequency strategies
die by costs" pitfall — the trade frequency required to isolate an intraday
session effect via daily enter/exit is structurally incompatible with the
repo's realistic 30bps round-trip cost model. Doubling costs (as required by
the falsification gate) makes it worse, not better.

The off-session mirror control also lost to buy-and-hold in the two cases
where it happened to hold slightly more capital than the US-session leg
(SOL, XRP), and lost even worse than the primary rule on BTC/ETH — there is
no evidence either half of the day disproportionately carries the return
once costs are applied; the entire result is cost-dominated, not
signal-dominated.

## Decisive blockers

1. Cost drag alone (~939% of capital) exceeds any plausible gross session
   effect before the mechanism is even evaluated.
2. Zero of 4 assets, zero of 12 partition-asset combinations pass the
   preregistered gate.
3. Doubled-cost check trivially fails (final capital ~1e-8 to 1e-6 of a $1
   start on all assets).

## Follow-up question

Any future test of intraday session-return concentration must use a much
lower-frequency implementation to survive costs — e.g. a weekly or monthly
rebalanced session-return TILT (partial exposure adjustment) rather than a
daily full flip, or measuring the effect purely descriptively (session vs
off-session realized return contribution) before ever proposing a tradeable
rule. Do not retest the daily-flip design on this cost model without a
fundamentally lower trade-frequency mechanism.

## Files

- `results/us_session_effect/runs/run-20260829T231553Z/strategy_summary.csv`
- `results/us_session_effect/runs/run-20260829T231553Z/partition_summary.csv`
- `results/us_session_effect/runs/run-20260829T231553Z/{BTC,ETH,SOL,XRP}_session_trades.csv`
