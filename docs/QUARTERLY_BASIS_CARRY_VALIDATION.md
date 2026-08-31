# BTC/ETH Quarterly Futures Basis Cash-and-Carry Validation

Run artifact: `results/quarterly_basis_carry/runs/run-20260831T064209Z/`

## Key findings

- **Primary rule tested:** at each real Binance daily close, if the current-quarter futures
  contract's annualized basis `(future_close/spot_close - 1) * 365/days_to_expiry` is **>= 8%**,
  enter a delta-neutral cash-and-carry trade (long spot + short the quarterly future, equal
  notional) at next day's open, hold to contract expiry (basis converges to ~0 by settlement),
  realize the captured basis net of 4-leg round-trip costs (spot buy/sell + futures short/cover
  at 15bps one-way each leg).
- **Data:** real Binance `continuousKlines` (CURRENT_QUARTER contractType) for BTC and ETH — the
  only two assets Binance lists dated/quarterly futures for — daily, 2021-02-03 through
  2026-07-27 (2,001/2,000 rows), newly fetched and cached this run
  (`data/quarterly_futures/{BTC,ETH}_quarterly_1d.csv.gz`), joined against already-cached
  Binance spot daily OHLCV. No proxy/synthetic basis.
- **Genuinely new mechanism/data source:** first use of Binance's dated/quarterly futures term
  structure in this repo — mechanistically distinct from every prior funding-based study
  (perpetual funding persistence, delta-neutral funding-carry, cross-exchange funding
  divergence). This trade harvests contango convergence to a *known expiry date*, not a
  persistence bet on a floating rate.

## Result table (primary rule)

| Asset | Final equity | Net return | Trades | Win rate | Top-trade PnL share | Spot B&H net return |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BTC | $10,067.20 | +0.67% | 5 | 100% | 42.0% | +50.43% |
| ETH | $10,049.41 | +0.49% | 7 | 71.4% | 60.2% | -15.30% |

## Verdict

**REJECTED (both assets, decisive).**

## Decisive blockers

1. **Zero trades in the holdout partition (2025-06-01 onward) on both BTC and ETH.** The
   preregistered 8% annualized-basis trigger has not fired since before mid-2025 — all 5 (BTC)
   and 7 (ETH) trades occurred in the 2021-2024 development/validation window. No genuine
   out-of-sample evidence exists for this exact threshold today.
2. **Economically tiny edge relative to costs.** Even where the trigger did fire, net returns
   were 0.5-0.7% cumulative over 4-5 years of capital — nowhere close to beating spot
   buy-and-hold on BTC (+50.4%), and only "beating" ETH's B&H because ETH's spot fell (-15.3%)
   over the same window, not because the carry trade itself was strong.
3. **ETH fails the doubled-cost check outright** (net return flips to -0.20%, loses to cash) —
   the captured basis is barely larger than the round-trip cost buffer.
4. **Concentration is high relative to the tiny edge**: single best trade = 42% (BTC) / 60%
   (ETH) of total strategy PnL, both over the program's 20% concentration cap, even though the
   dollar magnitudes involved are small.
5. Real annualized basis on Binance quarterly futures rarely and only briefly exceeds 8%
   (mean observed annualized basis ~15.7% but driven by a right-skewed distribython with a few
   extreme early-2021 contango spikes up to 23x; median is closer to 5.7%) — the threshold as
   specified captures only rare episodes concentrated in the 2021 bull-market futures-premium
   blowout, not a persistent structural premium.

## Files

- `results/quarterly_basis_carry/runs/run-20260831T064209Z/strategy_summary.csv`
- `results/quarterly_basis_carry/runs/run-20260831T064209Z/trade_log.csv`
- `results/quarterly_basis_carry/runs/run-20260831T064209Z/partition_summary.csv`
- `results/quarterly_basis_carry/runs/run-20260831T064209Z/config.json`
- `results/quarterly_basis_carry/runs/run-20260831T064209Z/REPORT.md`
- `data/quarterly_futures/BTC_quarterly_1d.csv.gz`, `data/quarterly_futures/ETH_quarterly_1d.csv.gz`
- `src/crypto_regime_backtest/quarterly_basis_carry_validation.py`
