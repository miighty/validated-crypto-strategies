# Cross-Sectional Amihud Illiquidity Premium Validation

EXP-2026-08-29-AMIHUD-001

Run: `.venv/bin/python3 scripts/amihud_illiquidity_cross_sectional.py`

## Hypothesis (preregistered, genuinely new)

Illiquid assets should command a return premium over liquid assets
(classic Amihud 2002 illiquidity-premium mechanism): investors demand
compensation for the higher price-impact cost of trading them. Tested
cross-sectionally: rank a 30-coin real Binance spot daily universe by a
rolling Amihud illiquidity ratio (mean |daily return| / dollar volume),
go long the most-illiquid tercile / short the most-liquid tercile
(dollar-neutral), rebalance weekly.

## Data

- Real Binance spot daily OHLCV, 30-coin universe (same set used in the
  residual-momentum study), `data/raw/*_1d.csv.gz`, 2020-01-01 through
  2026-07-27 (2,400 daily rows). Dollar volume approximated as
  `close * volume` (real Binance base-asset volume; no separate quote-volume
  column cached).
- No synthetic/proxy data used anywhere in the signal or execution.

## Design (frozen before results were inspected)

- Illiquidity ratio: `mean(|r|/dollar_volume)` over a rolling **14-day**
  window (min 10 obs), shifted 1 day (score at day t uses only data through
  t-1, no lookahead).
- Rebalance every 7 days, long top tercile (most illiquid) / short bottom
  tercile (most liquid), equal-weighted within each leg, 50%/50% gross split
  (dollar-neutral). Enter at next day's open, hold to next rebalance's entry.
- Costs: repo-standard 30bps round-trip, charged on turnover fraction of
  gross notional that changes membership.
- Control: seeded random-ranking L/S, identical leg sizes/turnover/cost
  structure.
- Fastest rejection criterion (preregistered): must beat the random-ranking
  control AND cash after costs, and no single trade may exceed 20% of total
  strategy net PnL (concentration cap).

## Result

| Strategy | Final USD | Trades | Sharpe | Total return | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
| Amihud illiquidity L/S | 9,719.65 | 341 | 0.11 | -2.80% | **Rejected** |
| Random-ranking L/S control | 3,210.50 | 343 | -0.71 | -67.90% | Baseline |
| Cash | 10,000.00 | 0 | n/a | 0.00% | Baseline |
| Equal-weight 30-asset buy-and-hold | 62,242.33 | 1 | 0.76 | +522.42% | Baseline |
| BTC buy-and-hold | 88,539.35 | 1 | 0.86 | +785.39% | Baseline |
| ETH buy-and-hold | 144,722.03 | 1 | 0.91 | +1347.20% | Baseline |
| SOL buy-and-hold | 224,950.74 | 1 | 1.02 | +2149.51% | Baseline |
| XRP buy-and-hold | 55,224.04 | 1 | 0.74 | +452.24% | Baseline |

## Honest conclusion

**REJECTED.** The illiquidity ranking does carry genuine (if weak) signal
over random legs — it clearly beats the seeded random-ranking control
($9,719.65 vs $3,210.50) — but it still **loses money net of costs**
(-2.80% total return) and finishes far behind cash and every buy-and-hold
benchmark. Concentration is also a concern: with near-zero net PnL, a single
trade's absolute PnL swamps the tiny net total (top_trade_pct_of_pnl ratio
> 100%, a symptom of the total PnL being close to zero rather than one
dominant trade driving a profitable outcome — either way it fails the
20% concentration cap).

Unlike the earlier Binance-universe Amihud study referenced in this skill's
own pitfalls section (top-30-market-cap universe, Sharpe 0.45, still failed
DSR), this is a fresh independent test on this repo's specific 30-coin
universe/cost model/rebalance cadence, and it does not even clear the first
gate (beat cash). No further parameter tuning is warranted on this exact
universe without a new mechanism — turnover costs (341 trades, 30bps
round-trip) consume essentially all of the weak illiquidity signal captured
here.

## Decisive blockers

1. Preregistered rejection criterion failed: does not beat cash
   (-2.80% vs 0.00%).
2. Loses decisively to every buy-and-hold benchmark (BTC/ETH/SOL/XRP/
   equal-weight-30), consistent with the repo's recurring finding that
   crypto's ~30-tradeable-perp universe is structurally too narrow for
   cross-sectional factor strategies to beat holding the strongest majors.
3. Concentration cap failed (near-zero net PnL means the ratio metric is
   uninformative/failing either way).

## Follow-up

Do not retest this exact 14-day/weekly/30-coin configuration without a new
mechanism. If Amihud illiquidity is revisited, a genuinely different
universe segment (e.g. small/mid-cap coins ranked ~100-400 by market cap,
per this skill's own prior guidance that illiquidity premia should be
stronger among genuinely thin names) would be a more promising next test
than retuning lookback/threshold on this same top-30 set.

## Files

- `results/amihud_illiquidity_cross_sectional/runs/run-20260829T140004Z/strategy_trades.csv`
- `results/amihud_illiquidity_cross_sectional/runs/run-20260829T140004Z/random_control_trades.csv`
- `results/amihud_illiquidity_cross_sectional/runs/run-20260829T140004Z/strategy_equity.csv`
- `results/amihud_illiquidity_cross_sectional/runs/run-20260829T140004Z/random_control_equity.csv`
- `results/amihud_illiquidity_cross_sectional/runs/run-20260829T140004Z/strategy_summary.csv`
- `results/amihud_illiquidity_cross_sectional/runs/run-20260829T140004Z/verdict.txt`
- `scripts/amihud_illiquidity_cross_sectional.py`
