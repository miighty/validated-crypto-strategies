# OI-Thin (Falling) Daily Breakout Continuation Validation

Run artifact: `results/oi_thin_breakout/runs/run-20260901T094943Z/REPORT.md`

## Hypothesis

Follow-up to the REJECTED OI-rising confirmation study (`EXP-2026-09-01-OIBREAKOUT-001`),
which explicitly recommended testing the opposite construction: OI *falling*
into a breakout (thin positioning, room to add fresh leverage) instead of OI
*rising* (which lost 2.7x-4.0x to the unconfirmed breakout control on every
asset).

Primary rule: long BTC/ETH/SOL/XRP at next daily open when close breaks above
the trailing prior-only 20-day high AND most recent completed daily open
interest is `<= -5%` versus 5 days earlier (mirror-image magnitude of the
rejected study's `+5%` trigger, not re-tuned). Exit at next open on first
close below the trailing prior-only 10-day low. 30bps round-trip cost.

## Data

Real Binance spot 1d OHLCV (already cached) + real Binance USD-M futures open
interest (already cached, `data/open_interest/*_oi_daily.csv.gz`, from the
public `data.binance.vision` archive). No synthetic/proxy data.

## Result

| Asset | OI-thin final | Unconfirmed breakout control | OI-rising variant (prior study) | Verdict |
|---|---:|---:|---:|---|
| BTC | $139,264 | $1,635,297 | $409,248 | REJECTED |
| ETH | $27,465 | $381,970 | $147,406 | REJECTED |
| SOL | $171,503 | $1,547,775 | $406,029 | REJECTED |
| XRP | $39,393 | $944,566 | $257,916 | REJECTED |

- OI-thin filter beats cash, buy-and-hold, DCA, and its own seeded
  random-timing control on all 4 assets, and survives doubled cost and
  best-trade-exclusion on all 4 — looks solid in isolation.
- Decisive failure: the OI-thin filter loses to the **unconfirmed breakout
  control** by 3.7x-11.8x on every asset — worse even than the previously
  rejected OI-rising variant, which itself already lost to the unconfirmed
  control by 2.7x-4.0x. Filtering by OI (in either direction) strictly
  removes profitable entries rather than curating better ones.
- Concentration cap (20%) also fails on ETH (43.5%), SOL (39.4%), XRP (65.2%)
  — only BTC (4.9%) is under cap, and it fails the primary economic-claim
  gate anyway.

## Verdict

**REJECTED** — decisive on all 4 assets, same primary-gate failure
(`beats_unconfirmed_breakout_control`) as the OI-rising study, and by a wider
margin. Neither direction of the OI-confirmation filter adds value to this
20-day-high/10-day-low breakout system.

## Conclusion for this program

Two consecutive tests (OI rising, OI falling) both show that filtering the
unconfirmed daily breakout system by any 5-day OI-change threshold destroys
value rather than adding it. This closes out the OI-confirmation family for
this exact breakout structure. The underlying unconfirmed breakout system
itself remains untested through the full validation ladder (walk-forward,
Monte Carlo, DSR, concentration-fix) — noted as a candidate for a dedicated
follow-up study, but any OI-based confirmation filter on it should be
considered a closed line of inquiry.

## Files

- `results/oi_thin_breakout/runs/run-20260901T094943Z/REPORT.md`
- `results/oi_thin_breakout/runs/run-20260901T094943Z/trades.csv`
- `results/oi_thin_breakout/runs/run-20260901T094943Z/partition_summary.csv`
- `results/oi_thin_breakout/runs/run-20260901T094943Z/manifest.json`
