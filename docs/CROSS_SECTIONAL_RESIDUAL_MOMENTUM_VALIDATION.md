# Cross-Sectional Residual Momentum Validation

Run artifact: `results/cross_sectional_residual_momentum/runs/run-20260829T042822Z/`

## Hypothesis (preregistered, docs/next_hypotheses.md rank #4)

Asset-specific demand may persist after removing the common crypto (BTC-beta)
factor from an asset's trailing return. Ranking **residual** 7-day returns
(raw return minus rolling-beta-implied BTC contribution) and going long the
top tercile was predicted to outperform **raw** (non-residualized) momentum
ranking and passive benchmarks after realistic costs.

## Design (frozen before results were inspected)

- **Universe:** 30 real Binance spot USDT daily coins (10 pre-existing core +
  20 newly fetched this run: LTC, BCH, XLM, ETC, VET, ZEC, DASH, THETA, ENJ,
  ZIL, BAT, IOST, ICX, ONT, NEO, QTUM, IOTA, TRX, ATOM, ALGO) — real Binance
  public spot klines only, no synthetic data.
- **Window:** 2020-01-01 through 2026-07-27 (2,400 daily bars).
- **Rolling BTC beta:** OLS slope of each asset's daily log return on BTC's,
  60-day trailing window (min 40 obs), shifted 1 day to avoid lookahead.
- **Momentum score:** trailing 7-day simple return per asset.
- **Residual score:** raw momentum minus `beta_t * BTC_7d_return`.
- **Rebalance:** weekly, long-only top tercile (~10 names), equal-weighted,
  enter at next day's open, hold to next rebalance's entry.
- **Costs:** 30 bps round-trip (repo standard: 10 bps fee + 5 bps slippage per
  side), charged on turnover fraction between rebalances.
- **Fastest rejection criterion (preregistered):** residual-momentum tercile
  must beat BOTH the raw-momentum tercile AND the equal-weight-30 buy-and-hold
  after costs, or it is rejected.

## Result table

| Strategy | Final USD ($10k start) | Total return | Sharpe | Max DD | Trades |
|---|---:|---:|---:|---:|---:|
| Residual momentum tercile | 78,083.71 | 680.8% | 0.77 | -74.5% | 337 |
| Raw momentum tercile (no beta-adjust) | 123,809.39 | 1138.1% | 0.85 | -77.5% | 342 |
| Equal-weight 30-asset buy-and-hold | 62,242.33 | 522.4% | 0.76 | -85.4% | 1 |
| BTC buy-and-hold | 88,539.35 | 785.4% | 0.86 | -76.6% | 1 |
| ETH buy-and-hold | 144,722.03 | 1347.2% | 0.91 | -79.3% | 1 |
| SOL buy-and-hold | 224,950.74 | 2149.5% | 1.02 | -96.3% | 1 |
| XRP buy-and-hold | 55,224.04 | 452.2% | 0.74 | -83.2% | 1 |

## Honest conclusion

**REJECTED.** Residual (beta-adjusted) momentum beat the equal-weight-30
benchmark but was clearly **outperformed by the simpler raw momentum
ranking** on the same universe/costs/schedule ($78.1k vs $123.8k final
capital, lower Sharpe). Removing the BTC-beta component did not add value —
it destroyed it. The beta-adjustment mechanism (persistent idiosyncratic
demand net of common-factor exposure) is not supported by this data; simple
momentum already captured more of the exploitable signal than the
"cleaner" residualized version.

Both cross-sectional strategies also trail single-asset BTC/ETH/SOL
buy-and-hold outright over this window — consistent with the skill's prior
finding that crypto's ~30-tradeable-perp universe is structurally too narrow
for cross-sectional factor strategies to earn a premium over simply holding
the strongest majors.

## Decisive blockers

1. Preregistered rejection criterion failed: residual momentum did not beat
   raw momentum (mandatory condition).
2. Even the winning raw-momentum tercile underperformed simple SOL/ETH
   buy-and-hold over the same window — no incremental edge from active
   rotation once turnover costs are included.

## Files

- `results/cross_sectional_residual_momentum/runs/run-20260829T042822Z/strategy_summary.csv`
- `results/cross_sectional_residual_momentum/runs/run-20260829T042822Z/residual_trades.csv`
- `results/cross_sectional_residual_momentum/runs/run-20260829T042822Z/raw_momentum_trades.csv`
- `results/cross_sectional_residual_momentum/runs/run-20260829T042822Z/residual_equity.csv`
- `results/cross_sectional_residual_momentum/runs/run-20260829T042822Z/raw_momentum_equity.csv`
- `results/cross_sectional_residual_momentum/runs/run-20260829T042822Z/verdict.txt`
- `scripts/cross_sectional_residual_momentum.py`
- `scripts/fetch_cross_sectional_universe.py` (fetched the 20 additional real Binance symbols)
