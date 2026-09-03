# Wick-Sensitive Panic-Flush + Price-Reclaim Confirmation (EXP-2026-09-03-FLUSHRECLAIM-001)

## Hypothesis

Every prior "buy the panic" study in this program (DVOL fear-spike, FGI
extreme-fear, volume-spike capitulation flush, NVT valuation-extreme,
Coinbase-premium contrarian, stablecoin-depeg rebound) bought **immediately**
on the trigger with a fixed forward hold, and every one was REJECTED — several
explicitly diagnosed the failure as "no price-reclaim confirmation, buying
into ongoing declines" and named a reclaim-confirmation filter as the
recommended follow-up. This study is the first in this repo to apply a genuine
reclaim-**confirmation gate** (wait for price to reclaim its own breach level
before committing capital) rather than a fixed-hold entry, on a wick-sensitive
(not close-based) panic-flush trigger.

## Data

Real Binance spot 1h OHLCV, BTC/ETH/SOL/XRP (`data/raw/*_1h.csv.gz`, already
cached). No new fetch required. Full available history through repo cutoff.

## Primary rule (frozen before any result inspected)

1. `prior_24h_high = high.shift(1).rolling(24).max()` (prior-only, no lookahead).
2. Flush trigger: `low_t <= prior_24h_high_t * 0.96` (>=4% intrabar wick drop).
3. `breach_level = prior_24h_high * 0.96`.
4. Confirmation window: within 24 bars after trigger, wait for the first bar
   whose **close** reclaims `>= breach_level`.
5. If confirmed: enter long at the **next bar's open**. If not confirmed
   within 24h, discard the event — no trade.
6. Exit: first of +3% profit target or 72h timeout, executed at the following
   bar's open.
7. Cooldown: no new triggers considered while awaiting confirmation or in
   position (one cascade -> at most one trade).
8. Costs: standard 30bps round trip.

## Results

| Asset | Flush events | Confirmed | Trades | Mean hold (h) | Primary final ($1 start) | B&H final | DCA final | Random-control final | Doubled-cost final | Best-trade-excluded final | Top-trade % PnL | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| BTC | 755 | 587 | 587 | 49.8 | 0.3112 | 4.6414 | 3.9953 | 0.7538 | 0.0533 | 0.4722 | 14.8% | REJECTED |
| ETH | 1016 | 782 | 782 | 46.3 | 0.0266 | 2.5780 | 3.4793 | 0.2476 | 0.0025 | 0.0422 | 57.8% | REJECTED |
| SOL | 1025 | 761 | 761 | 38.0 | 6.2684 | 25.9961 | 4.0576 | 1.2612 | 0.6370 | 9.1107 | -44.8% | REJECTED |
| XRP | 1084 | 846 | 846 | 47.4 | 0.0628 | 2.1290 | 2.2428 | 2.0149 | 0.0049 | 0.1009 | 5.9% | REJECTED |

Real 2025+ holdout trades on all 4 assets (BTC 75, ETH 120, SOL 152, XRP 135),
all with **negative mean trade return** in the holdout partition (-0.2% to
-1.3% per trade).

## Diagnosis

- The 4%-intrabar-wick-from-24h-high trigger is far too common (587-1084
  events per asset over the sample) to be a genuine rare panic/capitulation
  signal — it is picking up ordinary hourly volatility, the same failure mode
  documented in the already-rejected `VOLUME_FLUSH_REBOUND_VALIDATION.md`
  study (that one used a 3% close-to-close threshold and also fired 200-300
  times/asset).
- ~75-85% of flush events reclaim their breach level within 24h (587/755 BTC,
  782/1016 ETH, 761/1025 SOL, 846/1084 XRP) — the reclaim confirmation gate
  filters very little, because ordinary hourly noise reclaims small wicks
  routinely. Requiring a reclaim of only the breach line itself (not the
  pre-flush high) is too weak a bar to distinguish genuine capitulation
  bottoms from routine chop.
- 3/4 assets (BTC, ETH, XRP) lose capital outright even before doubled costs;
  SOL alone shows a nominal primary edge over $1 but still loses to
  buy-and-hold, DCA, and its own random-timing control.
- Doubled costs are catastrophic on all 4 assets (0.25%-64% of $1 remaining) —
  confirming this is fundamentally a **cost-dominated, over-frequent trigger**
  problem, not a marginal miss. ~600-1100 non-overlapping round trips at
  30bps/trip alone consume 180-330% of capital in cost drag before any signal
  value is assessed.
- Concentration is a secondary issue only (ETH's apparent tiny edge is
  entirely a single-trade artifact at 57.8%; BTC/XRP pass the 20% cap but
  still lose outright).

## Verdict

**REJECTED, decisively, on all 4 assets.** Zero of 8 preregistered gates
(beats cash/BH/DCA/random control, survives doubled cost, survives best-trade
exclusion, concentration ok, holdout trades) fully clear on any asset;
`beats_cash` itself fails on BTC/ETH/XRP.

## Lesson for future panic-flush studies

A reclaim-confirmation gate does **not** by itself fix an over-frequent
trigger — the trigger threshold must first be tightened enough that events are
genuinely rare (dozens per asset per multi-year sample, not hundreds-to-
thousands) before confirmation timing can add value. This closes the
"add reclaim confirmation" recommended-follow-up from the volume-flush/NVT/
DVOL rejection notes for this exact loose (4%, 1h) trigger definition. If
revisited: use a much larger flush threshold (e.g. >=10-15% from a longer
rolling high, or require multi-bar cumulative drawdown, not a single-bar
wick) to cut event frequency by an order of magnitude before re-testing
reclaim confirmation.

Items 1-3 in `docs/next_hypotheses.md` remain the highest-priority untested
single-asset/single-mechanism ideas; items 6-8 remain blocked on real
liquidation/order-flow data this repo does not have.
