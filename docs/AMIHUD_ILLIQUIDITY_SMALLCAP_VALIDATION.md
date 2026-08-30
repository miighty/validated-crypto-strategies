# Cross-Sectional Amihud Illiquidity Premium — Small/Mid-Cap Universe Validation

EXP-2026-08-30-AMIHUD-SMALLCAP-001

Run: `.venv/bin/python3 scripts/amihud_illiquidity_smallcap.py`
Robustness: `.venv/bin/python3 scripts/amihud_illiquidity_smallcap_robustness.py`
Significance: `.venv/bin/python3 scripts/amihud_illiquidity_smallcap_mc_test.py`
DSR: `.venv/bin/python3 scripts/amihud_illiquidity_smallcap_dsr.py`

## Hypothesis (preregistered, follow-up to already-REJECTED EXP-2026-08-29-AMIHUD-001)

The top-30-market-cap Amihud illiquidity study (`docs/AMIHUD_ILLIQUIDITY_CROSS_SECTIONAL_VALIDATION.md`)
failed to beat cash. This skill's own guidance and the reference literature hold
that illiquidity premia should be *stronger* among genuinely thin names, not
top-30 majors which are all fairly liquid to begin with. This is a new universe
segment test of the identical mechanism, not a retune of the rejected
configuration.

## Data (real, no proxy/synthetic inputs)

- Universe: live CoinGecko market-cap ranking (rank 100–400), cross-referenced
  against live Binance spot USDT-quoted TRADING pairs
  (`api.binance.com/api/v3/exchangeInfo`). Stablecoins/wrapped/liquid-staking
  tickers excluded.
- Final universe: **54 real coins** with real Binance spot daily OHLCV,
  each requiring >= 300 rows of history (`data/raw/*_1d.csv.gz`), analysis
  window 2020-01-01 through 2026-07-27 (2,400 daily rows).
- Core benchmarks (BTC/ETH/SOL/XRP) from the repo's existing cached universe.

## Design (identical mechanism/parameters to the rejected top-30 study — only
the universe changed, so any different result is attributable to universe
thinness, not methodology tuning)

- Illiquidity ratio: `mean(|daily return| / dollar_volume)` over rolling
  14-day window (min 10 obs), shifted 1 day (no lookahead).
- Rebalance every 7 days, long top tercile (most illiquid) / short bottom
  tercile (most liquid), equal-weighted within each leg, dollar-neutral
  50/50 gross split. Enter at next day's open, hold to next rebalance's entry.
- Costs: 30bps round-trip (repo standard).
- Control: seeded random-ranking L/S, identical leg sizes/turnover/cost.
- Preregistered fastest-rejection criterion: must beat random-ranking control
  AND cash after costs, no single trade > 20% of total net PnL.

## Primary result

| Strategy | Final USD | Trades | Sharpe | Total return | Max DD | Top-trade % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Amihud illiquidity L/S (small/mid-cap) | 77,485.87 | 314 | **1.43** | +674.86% | -22.1% | 8.9% |
| Random-ranking L/S control | 5,895.72 | 315 | -0.19 | -41.04% | -46.4% | 58.4% |
| Cash | 10,000.00 | 0 | n/a | 0.00% | 0.0% | n/a |
| Equal-weight 54-asset small/mid-cap B&H | 12,963.31 | 1 | 0.55 | +29.63% | -97.4% | n/a |
| BTC buy-and-hold | 88,539.35 | 1 | 0.86 | +785.39% | -76.6% | n/a |
| ETH buy-and-hold | 144,722.03 | 1 | 0.91 | +1347.20% | -79.3% | n/a |
| SOL buy-and-hold | 224,950.74 | 1 | 1.02 | +2149.51% | -96.3% | n/a |
| XRP buy-and-hold | 55,224.04 | 1 | 0.74 | +452.24% | -83.2% | n/a |

Beats random control: **True**. Beats cash: **True**. Concentration OK (≤20%): **True**.
First-pass verdict: **CANDIDATE** (clears all three preregistered gates).

## Robustness checks

| Check | Result |
| --- | --- |
| Doubled cost (60bps) | Final $70,025 (Sharpe unchanged 1.43) — still beats cash |
| 1-day execution delay | Final $95,195, Sharpe **1.59** (improves, not decays) — still beats cash |
| Walk-forward: 2020-01→2023-04 | Sharpe 1.47, 141 trades, top-trade 25.2% |
| Walk-forward: 2023-04→2026-07 | Sharpe 1.62, 173 trades, top-trade 12.1% |
| Best-trade exclusion | Total net PnL $67,485.87 → $61,501.35 excluding best trade; still strongly positive |
| Block-bootstrap 95% CI (mean trade return, n=5000, block=8) | mean 0.719%, CI [0.32%, 1.10%] — **excludes zero** |

No decay walk-forward (OOS Sharpe *higher* than in-sample first half), survives
doubled costs, survives 1-day delay (rules out same-bar lookahead artifact per
this skill's documented RSI-extremity false-positive pattern), survives
best-trade exclusion, bootstrap CI clearly excludes zero.

## Significance tests

**Cross-sectional Monte Carlo (correct null — label-scramble, not time-order
shuffle):** n_trials=500. Observed final capital $77,485.87 vs simulated
mean $5,537.41 (std $3,951.31, p95 $13,747.55). **p-value = 0.0000** (both on
final capital and Sharpe). Decisively significant — the illiquidity ranking
itself contains real information, not noise.

**Deflated Sharpe Ratio** (Bailey/Lopez de Prado, annualization-bug-corrected
per this skill's own pitfall — SE computed in per-bar units, converted back to
annualized terms), using this program's approximate true search size
(n_trials=84, conservative proxy = count of `results/*/runs/*` directories in
this repo as of this test):

- SR annualized: 1.43, SR per-bar: 0.198, SE per-bar: 0.054
- Skew: 0.59, excess kurtosis present (kurt=5.72)
- Expected max SR per bar under 84 trials: 0.134
- **DSR stat: 1.17, p-value: 0.121 — fails significance at 0.05**

## Honest conclusion

**PROMISING BUT FAILS THE PROGRAM'S MULTIPLE-TESTING BAR (near-miss, not a
clean PASS).** This is the strongest result in this program's cross-sectional
factor sweep to date:

- Clears every mechanical gate the prior four cross-sectional studies
  (Amihud-top30, funding-carry, residual-momentum, low-vol) all failed:
  beats cash, beats random control, concentration well under cap, no
  walk-forward decay, survives doubled costs and 1-bar delay.
- Cross-sectional Monte Carlo is decisive (p=0.0000) — the ranking signal is
  real, not a shuffle-null artifact.
- **But** Deflated Sharpe fails (p=0.121) once the program's actual variant
  search count (84 backtests) is accounted for. Per this skill's own
  documented distinction: MC answers "is this pattern distinguishable from
  random chance" (yes); DSR answers "is this pattern strong enough to trust
  after searching this many variants" (no, not yet at conventional 0.05).

This does **not** invalidate the finding — it means the strategy needs either
(a) a larger independent out-of-sample confirmation window, (b) a smaller
effective search count (this program will keep growing its variant count, so
DSR will only get harder to clear, not easier), or (c) cross-exchange
replication (Bybit/OKX) before committing capital, consistent with this
skill's magnitude-decay findings on the top-30 Amihud study (Binance headline
Sharpe was consistently the optimistic upper bound across venues).

**Verdict: PROMISING BUT INCONCLUSIVE at program significance threshold —
do not deploy on DSR grounds alone, but do not discard either.** Recommended
next step if resources allow: cross-exchange replication (Bybit real OHLCV
for the same 54-coin universe, subject to listing availability) before any
capital allocation decision.

## Files

- `results/amihud_illiquidity_smallcap/runs/run-20260830T022320Z/` (primary backtest)
- `results/amihud_illiquidity_smallcap/runs/robustness-20260830T022402Z/` (cost/delay/walk-forward/bootstrap)
- `results/amihud_illiquidity_smallcap/runs/mc_test-20260830T022642Z/` (cross-sectional MC)
- `results/amihud_illiquidity_smallcap/runs/dsr-20260830T022618Z/` (deflated Sharpe)
- `scripts/amihud_illiquidity_smallcap.py`
- `scripts/amihud_illiquidity_smallcap_robustness.py`
- `scripts/amihud_illiquidity_smallcap_mc_test.py`
- `scripts/amihud_illiquidity_smallcap_dsr.py`
