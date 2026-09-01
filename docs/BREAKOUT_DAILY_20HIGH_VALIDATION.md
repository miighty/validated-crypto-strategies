# Plain Daily 20-Day-High / 10-Day-Low Breakout Continuation -- Full Validation

## Hypothesis
The unconfirmed 20-day-high/10-day-low breakout system (no OI filter) that appeared as
a strong baseline inside both OI-confirmation studies (EXP-2026-09-01-OIBREAKOUT-001,
EXP-2026-09-01-OITHIN-001) is a genuine, tradeable edge on its own -- both prior studies'
registry notes flagged it as "an untested candidate for a dedicated full-validation-ladder
study" and explicitly deferred judgment on it since OI confirmation was the primary
hypothesis under test in those runs, not this system itself.

## CRITICAL: lookahead bug found and fixed during this study
The first implementation pass (mirroring the existing `oi_breakout_confirmation_validation.py`
code pattern verbatim) executed entries/exits at bar `i`'s own open using a signal computed
from bar `i`'s own close -- i.e. trading at today's open on information only available at
today's close. This is impossible in live trading and inflated results by ~100x (BTC first
pass: $13.26M final vs corrected $86.1k; SOL $306M vs $906k). **This same bug pattern exists
in the two prior OI-confirmation studies' "unconfirmed breakout control" baseline numbers**
(`oi_breakout_confirmation_validation.py` / `oi_thin_breakout_validation.py`, both use
`opens[i]` execution against `entries[i]`/`exit_breaks[i]` signals derived from bar `i`'s own
close) -- their primary OI-filtered verdicts are unaffected (OI-filtered variants still lost
to the (buggy, inflated) unconfirmed control by a wide margin, so REJECTED stands), but the
absolute dollar figures quoted for the "unconfirmed breakout control" in those two reports are
overstated and should not be read as a real achievable return. This module fixes the bug:
entries and exits now execute at the **next** bar's open at the earliest (`exec_offset = 1 +
delay_bars`), never the triggering bar's own open.

## Primary rule (frozen before inspecting corrected results)
- Entry: daily close > rolling 20-day high (prior-only, `shift(1)`, no lookahead). Enter at
  the *following* daily open.
- Exit: first daily close < rolling 10-day low (prior-only, `shift(1)`, no lookahead). Exit
  at the *following* daily open. Non-overlapping trades.
- Costs: 30bps round-trip.
- Universe: BTC/ETH/SOL/XRP, full available Binance spot daily history.

## Results (corrected, no-lookahead execution)

| Asset | Trades | Primary final | B&H final | DCA final | Random-control final | Doubled-cost | 1-bar delay | Best-trade-excl | Top trade % PnL | MC p-value | DSR p-value | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BTC | 62 | $86,093 | $46,414 | $40,002 | $24,003 | $78,431 | $72,309 | $49,316 | 8.4% | 0.060 | 0.451 | REJECTED |
| ETH | 62 | $177,994 | $25,780 | $34,806 | $58,016 | $162,153 | $176,985 | $75,412 | 29.9% | 0.067 | 0.264 | REJECTED |
| SOL | 43 | $906,379 | $259,961 | $40,677 | $155,041 | $849,640 | $1,974,152 | $205,695 | 12.4% | 0.115 | 0.191 | REJECTED |
| XRP | 54 | $83,657 | $21,290 | $22,419 | $404 | $77,134 | $75,631 | $22,557 | 97.9% | 0.230 | 0.565 | REJECTED |

All 4 assets: beats cash/BH/DCA/random-timing control, survives doubled cost, survives
best-trade exclusion, survives 1-bar execution delay, has real 2025+ holdout trades.

**Decisive blocker: zero of 4 assets clear Monte Carlo significance (bootstrap-resample null on
demeaned trade returns) at p<0.05, and zero clear Deflated Sharpe at the program's true search
size (n_trials=96).** ETH and XRP additionally fail the 20% concentration cap (29.9% and 97.9%
of total PnL respectively concentrated in a single trade).

## Verdict: REJECTED (decisive)
Every asset clears every economic/robustness gate (beats benchmarks, survives cost/delay
stress, has holdout evidence) but fails the two statistical-significance gates uniformly.
This is a different failure shape than the program's other near-misses (which typically pass
MC/DSR but fail concentration) -- here the strategy looks economically attractive on its face
but the trade count (43-62 per asset) is too small relative to the return dispersion for either
significance test to distinguish it from a lucky draw. Consistent with the skill's Sharpe
rubric: raw annualized Sharpe (per-bar, before DSR penalty) was 1.11-1.36, squarely in the
"marginal but tradeable if capacity/costs are cheap" tier -- not the 2.0+ needed to survive a
96-variant multiple-testing penalty.

## Follow-up notes
- Do not retest this exact 20-day-high/10-day-low breakout definition without a new
  robustness lever (larger universe for cross-sectional framing, or a materially longer
  history/more trades per asset).
- The lookahead-bug finding is the more consequential output of this run: any prior report in
  this repo whose "final capital" numbers for a daily-close breakout system came from
  `oi_breakout_confirmation_validation.py`'s or `oi_thin_breakout_validation.py`'s shared
  `simulate_long_strategy`/`simulate_random_control` functions used same-bar-open execution
  against a same-bar-close signal. Both of those studies' formal REJECTED verdicts are
  unaffected (the OI-filtered primary rule still lost to the control by a wide relative margin
  either way), but their reported absolute dollar totals for the *unconfirmed control* baseline
  are overstated by roughly 100x and should be disregarded as a return estimate.
