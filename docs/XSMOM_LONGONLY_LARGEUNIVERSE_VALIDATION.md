# Cross-sectional long-only top-decile momentum (75-coin universe) validation

EXP-2026-09-02-XSMOM-LONGONLY-001

Run: `.venv/bin/python3 scripts/xsmom_longonly_largeuniverse_validation.py`

## Hypothesis (preregistered)

Four prior cross-sectional dollar-neutral L/S factor studies on this repo's
30-coin universe (Amihud illiquidity, funding-carry, residual momentum,
low-volatility premium) all failed to beat cash, with each registry note
recommending either a materially larger universe or a non-dollar-neutral
(long-only) construction as the next step. This study implements the
long-only recommendation directly and on a larger universe: trailing 30-day
momentum, weekly rebalance, long top-decile equal-weighted, on all 75
Binance-listed coins in this repo with >=730 days of real daily history
(vs the prior 30-coin universe) -- genuinely new for this repo (first
long-only, no-short-leg cross-sectional construction; residual momentum was
dollar-neutral tercile L/S with beta-residualization).

## Data (real, no proxy/synthetic inputs)

Real Binance spot daily OHLCV, 75 coins (`data/raw/*_1d.csv.gz`, all already
cached), full available history through 2026-07-27, analysis window
2020-01-01 onward. Assets phase into eligibility once they individually
accumulate 90 days of trailing history (no lookahead into pre-listing gaps).

## Design

- Signal: trailing 30-day return, `shift(1)` applied (prior-only).
- Rebalance weekly; long top decile (`max(1, n//10)`) of eligible coins,
  equal-weighted, 100% invested, no short leg.
- Costs: repo-standard 30bps round-trip on turnover.
- Benchmarks: cash, BTC/ETH/SOL/XRP buy-and-hold, equal-weight-75-coin
  buy-and-hold, seeded random-decile-selection control (same N/turnover/cost
  structure).

## Result (full sample, 2020-01-01 through 2026-07-27)

| Strategy | Final ($10k start) | Sharpe |
| --- | ---: | ---: |
| Primary (long-only top-decile momentum) | $588,706 | 1.07 |
| Doubled cost | $396,464 | 1.01 |
| Random-decile control | $46,729 | 0.71 |
| Equal-weight-75-coin B&H | $30,264 | 0.64 |
| BTC B&H | $88,539 | 0.86 |
| ETH B&H | $144,722 | 0.91 |
| SOL B&H | $224,951 | 1.02 |
| XRP B&H | $55,224 | 0.74 |

- Beats cash, equal-weight universe B&H, random control, all 4 majors, and
  survives doubled cost on the full sample.
- Cross-sectional label-scramble Monte Carlo (n=200, shuffling which coins
  land in the long decile each rebalance, same turnover/cost/size): observed
  final capital sits at the **99.5th percentile** of the random-selection
  null distribution (p=0.005) -- the ranking signal is not attributable to
  chance on the full sample.
- **Concentration cap decisively violated**: single best rebalance block
  (2024-11-27, long XLM/ADA/XRP/DOGE/ALGO/SAND/CVX, +47% weighted return)
  contributes 130% of total net PnL. Excluding the top 3 blocks alone drops
  final capital from $589k to $199k (-66%).
- Walk-forward: first-half Sharpe 1.43 vs second-half 0.58 -- meaningful
  decay.

## Decisive holdout failure (2025-01-01 through 2026-07-27, 82 trades)

Rebasing $10,000 strictly at the start of the holdout partition (no carry-in
compounding from prior gains):

| Strategy | Holdout final | Holdout return |
| --- | ---: | ---: |
| Primary strategy | $3,406 | -65.9% |
| Equal-weight-75-coin B&H | $3,433 | -65.7% |
| BTC B&H | $6,740 | -32.6% |
| ETH B&H | $5,632 | -43.7% |
| SOL B&H | $3,819 | -61.8% |
| XRP B&H | $4,570 | -54.3% |

The strategy **loses outright in the true out-of-sample partition**,
essentially matching the passive equal-weight-universe benchmark (both down
~66%) and losing decisively to every one of the four major buy-and-hold
benchmarks. The full-sample headline numbers were driven almost entirely by
a handful of 2021-2025 altcoin-momentum blocks (concentration cap failure
above) that did not repeat in the 2025+ regime.

## Verdict

**REJECTED** (decisive). The cross-sectional MC test confirms the momentum
ranking signal is statistically distinguishable from random selection on
the full sample, but this does not translate into a deployable edge:
(1) concentration cap violated (130% of PnL from one block, compounding to
-66% of final capital when the top 3 blocks are excluded), and (2) the
strategy loses outright to every benchmark including passive equal-weight
in the 2025+ holdout, the program's standard decisive rejection gate. This
closes out the "long-only, larger-universe" cross-sectional momentum
follow-up recommended by four prior rejected L/S factor studies -- moving
to a non-dollar-neutral, larger-universe construction did not resolve the
underlying problem, it relocated it: instead of costs eating a weak signal
(the L/S studies' failure mode), a genuinely real-but-concentrated signal
decayed hard exactly when it mattered (2025+).

## Files

- `results/xsmom_longonly_largeuniverse/runs/run-20260902T112706Z/summary.csv`
- `results/xsmom_longonly_largeuniverse/runs/run-20260902T112706Z/trades.csv`
- `results/xsmom_longonly_largeuniverse/runs/run-20260902T112706Z/verdict.txt`
- `scripts/xsmom_longonly_largeuniverse_validation.py`
- `scripts/xsmom_mc_test.py` (cross-sectional label-scramble MC, n=200)
- `scripts/xsmom_test_partition_check.py` (2025+ holdout rebase check)
