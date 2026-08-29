# Cross-sectional low-volatility premium validation

Run: `.venv/bin/python3 scripts/volatility_premium_cross_sectional.py`

## Hypothesis (preregistered)

Leverage-constrained crypto traders bid up high-realized-volatility/high-beta
assets to embed extra leverage exposure (Frazzini-Pedersen "betting against
volatility" mechanism, applied cross-sectionally). Dollar-neutral long
lowest-realized-vol tercile / short highest-vol tercile, weekly rebalance,
should earn a premium net of costs.

## Design

- Universe: same 30-coin real Binance spot USDT daily universe used by the
  Amihud/momentum/funding-carry studies (`data/raw/*_1d.csv.gz`),
  2020-01-01 -> 2026-07-27 (2,400 daily rows).
- Score: rolling 21-day stdev of daily returns, `shift(1)` applied (no
  lookahead), min 15 observations.
- Weekly rebalance, long bottom tercile (lowest vol) / short top tercile
  (highest vol), equal-weighted per leg, dollar-neutral, 30bps round-trip
  cost on turnover.
- Control: seeded random-ranking L/S, identical mechanics.
- Benchmarks: cash, BTC/ETH/SOL/XRP buy-and-hold, equal-weight-30 buy-and-hold.

## Result

| Strategy | Final USD | Trades | Sharpe | Max DD | Top-trade % of PnL | Verdict |
|---|---:|---:|---:|---:|---:|---|
| Low-vol/High-vol L/S | 9,936.34 | 340 | 0.12 | -33.9% | 2,694% | **Rejected** |
| Random-ranking L/S control | 3,632.48 | 343 | -0.73 | -64.8% | 16.1% | Baseline |
| Equal-weight-30 BH | 62,242.33 | 1 | 0.76 | -85.4% | n/a | Baseline |
| BTC BH | 88,539.35 | 1 | 0.86 | -76.6% | n/a | Baseline |
| ETH BH | 144,722.03 | 1 | 0.91 | -79.3% | n/a | Baseline |
| SOL BH | 224,950.74 | 1 | 1.02 | -96.3% | n/a | Baseline |
| XRP BH | 55,224.04 | 1 | 0.74 | -83.2% | n/a | Baseline |
| Cash | 10,000.00 | 0 | n/a | 0.0% | n/a | Baseline |

## Honest conclusion

> **Rejected.** The low-vol/high-vol L/S lost money net of costs (-0.64%
> total return over 6.5 years, 340 trades) despite beating the seeded
> random-ranking control (confirming a weak but genuine ranking signal —
> low-vol names really do outperform high-vol names on a relative basis).
> It failed both fastest-rejection gates: (1) it did not beat cash, and
> (2) it badly failed the concentration cap — a single trade accounted for
> ~27x the strategy's tiny net PnL, meaning the reported near-zero total
> return is itself an artifact of one outlier trade offsetting many small
> losses, not a stable edge. It also lost decisively to every buy-and-hold
> benchmark (BTC/ETH/SOL/XRP/equal-weight-30), consistent with every prior
> cross-sectional L/S study in this repo (Amihud illiquidity, funding carry,
> residual momentum) — this repo's ~30-coin tradeable universe appears
> structurally too narrow for cross-sectional dollar-neutral factor
> strategies to clear the cost/concentration bar, regardless of the specific
> factor tested.

## Decisive blockers

1. Does not beat cash after 30bps round-trip costs (-0.64% total return).
2. Concentration cap badly violated (2,694% of PnL from one trade vs the
   20% cap) — signals PnL instability, not real edge.
3. Loses to every buy-and-hold benchmark by a wide margin.

## Files

- `results/volatility_premium_cross_sectional/runs/run-20260829T170349Z/strategy_summary.csv`
- `results/volatility_premium_cross_sectional/runs/run-20260829T170349Z/strategy_trades.csv`
- `results/volatility_premium_cross_sectional/runs/run-20260829T170349Z/random_control_trades.csv`
- `results/volatility_premium_cross_sectional/runs/run-20260829T170349Z/verdict.txt`
