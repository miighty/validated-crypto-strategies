# Google Trends "Bitcoin" Search-Interest Euphoria Contrarian Regime Validation

Run: `.venv/bin/python3 scripts/gtrends_euphoria_regime_validation.py`
Data fetch: `.venv/bin/python3 scripts/fetch_google_trends.py`
Artifact: `results/gtrends_euphoria_regime/runs/run-20260904T.../`

## Hypothesis (preregistered)

First genuinely new, non-market-derived **retail attention** data source in
this program: real Google Trends weekly worldwide search interest for
"bitcoin" (2017-05 through 2026-08, 484 weekly points, stitched from 3
overlapping pytrends queries via standard overlap-ratio rescaling — real
fetched values throughout, no synthetic data).

Mechanism: classic "sell the euphoria" contrarian — a search-interest spike
(z-score >= 2.0 vs trailing prior-only 52-week mean/std) marks retail-driven
local tops; go to CASH during extreme-attention weeks, stay long BTC/ETH/
SOL/XRP otherwise. This is the mirror image of every prior "buy the panic"
study in this program (DVOL, FGI, volume-flush, NVT, panic-flush-reclaim),
all of which were rejected — this tests the opposite direction (exit on
euphoria) with a genuinely external, non-price/non-derivatives signal.

## Design

- One-week execution lag (regime decided on week t close, position changes
  at week t+1 start).
- 30bps round-trip cost.
- Partitions: development (listing→2020), validation (2020→2023),
  test (2023→cutoff).
- Benchmarks: buy-and-hold, naive BTC-momentum regime control, seeded
  random-regime control (same block count/on-fraction).
- Falsification: primary must beat B&H + momentum control + random control
  on ≥3/4 assets, survive doubled cost, clear 20% concentration cap, not
  lose in test partition. Any decisive multi-gate failure → REJECTED.

## Result

Regime "on" (long) 92.3% of sample — extreme-euphoria weeks (z≥2.0) fired
231/2,984 days. 12–17 regime blocks per asset.

| Asset | Primary final | B&H final | Momentum ctrl | Random ctrl | Concentration | Test partition |
|---|---:|---:|---:|---:|---:|---|
| BTC | 4.81x | 8.69x | 4.54x | 0.94x | 35.3% (fails) | loses (1.40x vs 3.84x) |
| ETH | 1.22x | 3.32x | 8.32x | 14.30x | 77.1% (fails) | loses (0.61x vs 1.58x) |
| SOL | 6.18x | 22.50x | 245.4x | 128.6x | 33.0% (fails) | loses (0.76x vs 7.43x) |
| XRP | 0.97x | 1.76x | 7.84x | 1.60x | 63.4% (fails) | loses (0.75x vs 3.15x) |

- 0/4 beat buy-and-hold, 1/4 beat momentum control (BTC only, itself a weak
  win: 4.81x vs 4.54x), 1/4 beat random control (BTC only).
- 0/4 survive doubled cost, 0/4 survive best-block exclusion, 0/4 clear the
  20% concentration cap.
- 0/4 pass the untouched 2023+ test partition — every asset loses to
  buy-and-hold decisively in the held-out window.

## Verdict: REJECTED (decisive)

Exiting to cash on retail search-attention spikes destroys far more value
than it protects. The strategy misses too much of each asset's subsequent
uptrend (evident from the momentum control beating it by 2–200x on 3/4
assets) — extreme search interest, in this sample, is not reliably followed
by a durable drawdown; it's frequently a mid-rally checkpoint, not a top.
This confirms the "attention marks a top" thesis does not hold at a 52-week
z-score threshold on this instrument, joining the "buy the panic" rejection
family as its mirror-image "sell the euphoria" counterpart — both directions
of retail-sentiment timing have now failed in this program.

## Do not retest

This exact 52-week z≥2.0 weekly Google Trends euphoria-exit construction.
If revisited, would need either a fundamentally different filter (partial
de-risking rather than full flat, or combining with a price-based
confirmation of an actual reversal rather than acting on the search spike
alone) and a new economic rationale — not a plain threshold retune. Real
stitched Google Trends data is now cached
(`data/google_trends/bitcoin_search_interest_weekly.csv.gz`) for any future
attention-based follow-up.
