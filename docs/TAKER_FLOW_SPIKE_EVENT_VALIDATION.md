# Taker Buy-Ratio Spike Event-Trigger Validation

Run artifact: `results/taker_flow_spike_event/runs/run-20260904T082017Z/`

## Hypothesis

A single day's aggressor-side (taker) buy-volume ratio spiking to a
z-score >= +2.0 vs its own trailing prior-only 90-day history reflects a
burst of aggressive spot buying that should predict short-term (5-day)
continuation — a discrete EVENT-trigger construction on the same real
Binance spot data already used by the already-REJECTED slow-SMA
`TAKER_FLOW_TREND` regime study (EXP-2026-09-03-TAKERFLOW-001), but a
distinct mechanism (fast oscillator, not a trend filter).

## Design

- Data: real Binance spot hourly klines, `data/taker_flow/*_taker_flow_1h.csv.gz` (already cached, zero new fetch).
- Signal: daily volume-weighted taker-buy ratio, z-scored vs a prior-only trailing 90-day window (excludes the trigger day itself).
- Entry: 1-day lag after trigger day close, hold 5 days, 2-day cooldown, non-overlapping.
- Costs: 30bps round trip.
- Delay-robustness gate (per skill's fast-oscillator pitfall): also ran a 2-day-lag variant and required >50% Sharpe retention + still-positive return.

## Result table

| Asset | Trades | Primary final | Delayed final | B&H final | Random control | Concentration | Delay-robust |
|---|---:|---:|---:|---:|---:|---:|---:|
| BTC | 78 | 1.27x | 0.56x | 9.36x | 2.12x | 46.5% (fail) | No |
| ETH | 77 | 1.51x | 1.06x | 5.00x | 1.03x | 29.1% (fail) | Yes |
| SOL | 47 | 1.09x | 0.52x | 36.55x | 1.40x | 132.8% (fail) | No |
| XRP | 57 | 8.37x | 4.56x | 2.48x | 0.61x | 38.7% (fail) | Yes |

Gates: Beats B&H 1/4, Beats random control 2/4, Survives doubled cost 1/4,
**Concentration OK 0/4**, Excl-best-trade OK 1/4, Delay-robust 2/4, Test
partition pass 4/4 (all 4 assets beat B&H in the test slice, but that
partition is dominated by a broad crypto drawdown where B&H itself lost
money — a weak signal, not evidence of edge).

## Honest conclusion

> **Rejected, decisively.** 0/4 assets clear the 20% single-trade
> concentration cap — every asset's apparent edge (where any exists) is
> dominated by 1-2 outlier trades, the same failure signature as every
> other event-trigger positioning study in this program. BTC and SOL lose
> outright to buy-and-hold by a wide margin (9.36x and 36.55x respectively)
> and fail the delay-robustness gate (Sharpe flips negative under a single
> extra day of execution lag), the same same-bar-reactivity artifact this
> skill explicitly warns about for fast oscillators. Only XRP shows a
> superficially attractive result (8.37x, beats B&H/random/doubled-cost) but
> even XRP fails the concentration cap (38.7% of total PnL in one trade).

## Decisive blockers

1. **Concentration cap violated on all 4 assets** (29%-133% of PnL in a
   single trade) — this is now the 13th single-asset event-trigger/
   positioning-style study in this program to hit this exact failure mode.
2. **Delay-robustness gate fails on BTC/SOL** — Sharpe sign flips negative
   under a 1-extra-day execution lag, consistent with the "fast oscillator
   same-bar artifact" pitfall (an aggressive one-day buy spike is
   mechanically correlated with that day's own price move, not
   independently predictive).
3. BTC and SOL lose outright to buy-and-hold by 7-33x.

## Closing this line of research

Both constructions of Binance spot taker-flow data (slow SMA trend regime
filter, and now this fast z-score event trigger) have been tested and
REJECTED. Do not retest taker-flow-ratio signals on this universe without a
fundamentally different construction (e.g. cross-sectional taker-flow
ranking, which has not been attempted). Items 1-3 in `next_hypotheses.md`
remain the highest-priority untested single-asset/single-mechanism ideas.

## Files

- `results/taker_flow_spike_event/runs/run-20260904T082017Z/strategy_summary.csv`
- `results/taker_flow_spike_event/runs/run-20260904T082017Z/partition_summary.csv`
- `results/taker_flow_spike_event/runs/run-20260904T082017Z/{BTC,ETH,SOL,XRP}_trades.csv`
