# OI-Confirmed Daily Breakout Continuation Validation

## Hypothesis

A daily-close breakout above the trailing prior-only 20-day high, confirmed by
open interest rising >=5% over the prior 5 days (indicating fresh leveraged
demand rather than short-covering/noise), should outperform an unconfirmed
breakout after costs. Genuinely new mechanism for this repo: first long-side
use of real Binance OI data (prior OI use was short-side only, in
`crowded_perp_unwind_validation.py`), and a structural daily-timeframe
breakout distinct from the already-rejected 4h compression-filtered breakout
and SMA(200) trend studies.

## Data

- Real Binance spot 1d OHLCV, BTC/ETH/SOL/XRP (`data/raw/*_1d.csv.gz`, already cached).
- Real Binance USD-M futures open interest (`data/open_interest/*_oi_daily.csv.gz`,
  already cached this program from the public `data.binance.vision` daily-metrics
  archive). No synthetic/proxy OI. Sample restricted to each asset's real OI
  coverage start (BTC 2020-09-01, ETH/SOL/XRP 2021-12-01).

## Primary rule (preregistered)

1. Breakout: close > trailing prior-only 20-day high (shift(1), no lookahead).
2. OI confirmation: most recent completed daily OI snapshot >= +5% higher than
   5 days earlier (identical threshold to the already-tested short-side study).
3. Joint signal -> enter long at next daily open.
4. Exit: first close below trailing prior-only 10-day low -> exit at next open.
5. Costs: 30bps round-trip.

## Result

| Asset | Trades | Primary final | Unconfirmed-breakout control final | B&H | DCA | Concentration | Holdout trades |
|---|---:|---:|---:|---:|---:|---:|---:|
| BTC | 31 | $409,248 | **$1,635,297** | $54,646 | $16,838 | 3.1% | 7 |
| ETH | 24 | $147,406 | **$381,970** | $4,081 | $8,650 | 4.1% | 8 |
| SOL | 21 | $406,029 | **$1,547,775** | $3,553 | $14,488 | 24.3% (fails cap) | 6 |
| XRP | 25 | $257,916 | **$944,566** | $10,662 | $15,548 | 48.2% (fails cap) | 9 |

All 4 assets: beats cash, buy-and-hold, DCA, seeded random-timing control;
survives doubled cost and best-trade exclusion; has real 2025+ holdout trades
(6-9 per asset, unlike most prior rejections in this program which failed on
zero holdout trades). **But the OI confirmation filter itself is the decisive
loser: on every single asset, the unconfirmed breakout control (identical
20-day-high entry / 10-day-low exit, no OI gate) outperforms the OI-confirmed
version by 2.7x-4.0x.** SOL and XRP additionally violate the 20% concentration
cap even with the OI filter applied.

## Verdict

**REJECTED** (decisive on all 4 assets — fails `beats_unconfirmed_breakout_control`
gate universally, the primary economic claim under test).

## Why

The OI-rise filter does not identify a superior subset of breakouts; it simply
throws away most of the profitable ones. Requiring recently-added leverage
alongside a breakout systematically excludes early-stage/organic breakouts
that go on to run further (both the unconfirmed control and the confirmed
version share the same 10-day-low exit, so the difference is 100% attributable
to which entries the OI gate lets through). This is the opposite of the
mechanism's stated rationale — real open-interest data adds no value here,
it actively curates for worse trades.

## Follow-up

- Do not retest this exact OI-rise-as-breakout-filter mechanism; if OI is
  revisited on the long side, a materially different construction is needed
  (e.g. OI *falling* into a breakout — thin positioning, room to add — rather
  than OI already rising into it).
- The underlying unconfirmed 20-day-high/10-day-low breakout system itself
  looks strong pre-cost-model-scrutiny (all 4 assets crush B&H/DCA/random) but
  was not the primary hypothesis under test here and has NOT been put through
  the full validation ladder (walk-forward, Monte Carlo, DSR, concentration
  fix) — it is a candidate for a dedicated follow-up study in its own right,
  separate from the OI-confirmation question this run answered.
- Items 1-3 in `next_hypotheses.md` (compression filter, funding
  persistence/mean-reversion sort, BTC->alt delayed response) remain
  untested single-asset/single-mechanism ideas.
