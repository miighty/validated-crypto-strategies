# Deribit DVOL Fear-Spike Contrarian Rebound Validation

Run: `results/dvol_fear_spike/runs/run-20260830T114757Z/`

## Hypothesis (preregistered)

Deribit's DVOL (crypto's VIX-equivalent, real published implied-volatility
index from options market pricing) spiking >= 2 standard deviations above its
trailing 30-day mean signals acute fear/forced deleveraging that is often
overpriced relative to the eventual outcome (the documented TradFi VIX-spike
mean-reversion effect). Buying spot BTC/ETH on such a spike, holding 7 days,
should beat buy-and-hold and DCA after realistic costs.

Genuinely new for this repo: first study to use Deribit DVOL (a data source no
prior study in `docs/experiment_registry.md` has touched), and mechanistically
distinct from every prior study (not calendar, not cross-sectional factor, not
realized-vol, not event-odds, not SMA-trend).

## Design

- Universe: BTC, ETH only — DVOL is published only for these two by Deribit;
  no proxy/synthetic vol index was used for SOL/XRP (data doesn't exist, so
  they're excluded, not faked).
- Data: real Deribit public `get_volatility_index_data` API, daily resolution,
  2021-03-28 (earliest available) through 2026-08-30. Real Binance spot 1h
  OHLCV (`data/raw/{BTC,ETH}_1h.csv.gz`) for execution.
- Signal: `z = (DVOL_t - mean(DVOL_{t-30..t-1})) / std(DVOL_{t-30..t-1})`
  (rolling window shifted, prior-only, no lookahead).
- Entry: z >= 2.0 at a completed UTC day close -> enter spot long at next
  day's 00:00 UTC open (1-day info lag). Exit: fixed 7-day hold. Non-
  overlapping trades (cooldown until prior position closes).
- Costs: repo-standard 30bps round trip.
- Partitions: development 2021-03-28→2023-01-01, validation →2024-07-01,
  test →2026-08-30.
- Falsification: primary must beat B&H AND DCA on both assets, survive
  doubled cost, survive best-trade exclusion, and not lose in the test
  partition. Any failure -> REJECTED.

## Result

| Asset | Trades | Primary final | Doubled-cost final | Excl-best-trade final | B&H final | DCA final | Beats B&H | Beats DCA |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| BTC | 39 | 1.2264 | 1.0943 | 0.9693 | 1.1381 | 1.5108 | Yes | No |
| ETH | 46 | 1.0537 | 0.9206 | 0.8133 | 1.1070 | 0.8402 | No | Yes |

Test-partition pass: BTC fails (0.956 vs B&H 1.013), ETH passes (0.814 vs
B&H 0.550) — inconsistent across assets.

## Honest conclusion

**REJECTED.** No single asset clears all preregistered gates:
- BTC beats B&H but loses to DCA, fails doubled cost, fails best-trade
  exclusion, and fails the test partition.
- ETH beats DCA but loses to B&H, fails doubled cost, fails best-trade
  exclusion, though it does pass the test partition.
- Zero of 2 assets survive either the doubled-cost or best-trade-exclusion
  hostile checks — the DVOL fear-spike signal's apparent edge (where present
  at all) is cost-fragile and concentrated in a handful of trades, not a
  robust mean-reversion effect.

## Decisive blockers

1. Doubled round-trip cost flips both assets' primary result below 1.0
   (net loss), confirming the raw edge (if any) is thin relative to the
   30bps cost model.
2. Excluding the single best trade drops both assets below their own
   buy-and-hold benchmark, indicating concentration risk consistent with
   this program's recurring "single lucky trade" pattern.
3. Results are asset-inconsistent (BTC beats B&H/fails DCA; ETH the mirror),
   which is itself evidence against a shared, general fear-spike mechanism
   rather than asset-idiosyncratic noise.

## Follow-up question

Do not retest the 2-std/7-day DVOL spike rule on this universe without a
fundamentally different filter (e.g. combining DVOL spike with a
confirmation/reclaim price trigger, or testing DVOL-implied skew rather than
level). DVOL only exists for BTC/ETH on Deribit, so this mechanism cannot be
broadened to a larger cross-sectional universe — any future revisit stays a
2-asset, single-mechanism study.

## Files

- `results/dvol_fear_spike/runs/run-20260830T114757Z/strategy_summary.csv`
- `results/dvol_fear_spike/runs/run-20260830T114757Z/partition_summary.csv`
- `results/dvol_fear_spike/runs/run-20260830T114757Z/{BTC,ETH}_trades.csv`
- `data/deribit_dvol/{BTC,ETH}_dvol_1d.csv.gz` (real Deribit DVOL cache)
- `scripts/dvol_fear_spike_validation.py`
