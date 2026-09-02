# Daily 20-Day-High Breakout + ATR Volatility-Compression Filter -- Validation

## Hypothesis
next_hypotheses.md item #1 (rank 1, "Volatility compression followed by
accepted breakout"): dealers/short-vol participants may be forced to chase a
move that persists beyond a compressed inventory range, so gating breakout
entries on a prior LOW-volatility regime should beat accepting breakouts
unconditionally. Previously tested only on a 4h ATR/Bollinger-width breakout
system (`breakout_compression_validation.py`, REJECTED). This run applies the
identical compression-filter idea to the DAILY 20-day-high/10-day-low
breakout system that was just run through the full validation ladder
(EXP-2026-09-01-BREAKOUT20HIGH-001, REJECTED on statistical significance) --
a genuinely new timeframe/parent-system combination for this exact mechanism.

## Primary rule (frozen before inspecting filtered results)
- Entry: daily close > prior-only rolling 20-day high AND the prior-only
  trailing 252-day percentile rank of ATR(14)/close <= 30 (bottom-30%
  realized-vol regime at the signal bar). Enter at next daily open.
- Exit: identical to parent (first close < prior-only rolling 10-day low).
  Exit at next daily open. Non-overlapping trades.
- Costs: 30bps round-trip.
- Universe: BTC/ETH/SOL/XRP, full available Binance spot daily history.
- **Primary falsification criterion (frozen, from next_hypotheses.md item
  #1):** the filtered rule must beat the unfiltered-breakout control
  (identical exit logic, entry = raw breakout with no compression gate) --
  "no improvement in validation net return... vs acceptance without
  compression" is the stated fastest-rejection criterion.

## Results

| Asset | Trades | Filtered final | Unfiltered control final | B&H | Beats control? | Concentration | MC p | DSR p | Verdict |
|---|---:|---:|---:|---:|---|---:|---:|---:|---|
| BTC | 34 | $59,579 | $86,093 | $46,414 | **No** | 18.0% (ok) | 0.081 | 0.479 | REJECTED |
| ETH | 39 | $65,185 | $177,994 | $25,780 | **No** | 31.2% (fails) | 0.036* | 0.505 | REJECTED |
| SOL | 28 | $189,410 | $906,379 | $259,961 | **No** | 20.6% (fails) | 0.164 | 0.494 | REJECTED |
| XRP | 39 | $53,655 | $83,657 | $21,290 | **No** | 94.5% (fails) | 0.316 | 0.674 | REJECTED |

\* ETH's Monte Carlo test alone is significant, but this is the compression
study's own return-shuffle null on the FILTERED trade sequence, not a pass on
the decisive gate under test (beating the unfiltered control).

## Honest conclusion

**REJECTED, decisive, on the exact falsification criterion preregistered in
next_hypotheses.md item #1.** The compression filter loses to the unfiltered
breakout control on **all 4 assets**, by margins of 1.3x (XRP) to 4.8x (SOL).
Filtering entries down to only the ~30% lowest-realized-vol regime cuts trade
count by roughly half (28-39 vs 43-62) and removes far more profitable
entries than it removes false/noisy ones -- the same failure pattern already
seen when OI-based filters were bolted onto this identical breakout system
(EXP-2026-09-01-OIBREAKOUT-001, EXP-2026-09-01-OITHIN-001, both REJECTED for
losing to the unfiltered control). Additionally, 3/4 assets now fail the 20%
concentration cap under the filtered rule (they passed concentration in the
unfiltered parent study) -- removing "noisy" high-vol breakouts concentrates
the remaining PnL into fewer, larger blocks rather than curating a cleaner
signal.

This closes the compression-filter family for both breakout systems tested
in this repo (4h ATR/Bollinger and daily 20d-high/10d-low) -- both REJECTED
for the identical reason (filter removes value, doesn't add it). Do not
retest a volatility-compression gate on either breakout system without a
fundamentally different construction (e.g. requiring compression on the
EXIT side, or using compression as a position-sizing multiplier rather than
a binary entry filter).

next_hypotheses.md items #2 (funding persistence vs mean-reversion -- already
substantially explored via funding-carry studies) and #3 (BTC shock -> delayed
altcoin response -- already tested and REJECTED, docs/BTC_ALT_RESPONSE_VALIDATION.md)
are effectively closed too; items #6-8 (liquidation exhaustion/cascade,
spot-vs-perp lead/lag) remain blocked on data this repo does not have
(no real liquidation-print feed, no fine-grained spot/perp trade-level data).

## Artifact
`results/breakout_daily_compression/runs/run-20260902T212635Z/REPORT.md`
