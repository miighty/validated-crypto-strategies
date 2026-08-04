# Research Constitution

This constitution applies to every experiment in the minimum viable edge-research workflow. A historical profit is an observation, not proof of an edge.

## Required hypothesis fields

Every experiment must freeze the following before its untouched test period is inspected:

- Strategy name and experiment ID.
- Economic mechanism.
- Market participants expected to pay the strategy.
- Required data.
- Exact signal definition.
- Entry rule and information timestamp.
- Exit rule.
- Stop or risk rule.
- Position-sizing method.
- Expected holding period.
- Expected market regime.
- Expected failure mode.
- Development period.
- Validation period.
- Untouched test period.
- Primary performance metric.
- Baselines.
- Falsification criteria.

Signals may use only completed candles. Unless explicitly justified otherwise, a signal at candle close is executed at the next candle open. UTC is the only time zone. Failed experiments and their frozen specifications remain in the registry.

## Default rejection and downgrade criteria

Reject or downgrade a strategy when any of the following occur:

- It is unprofitable after realistic costs.
- It depends on same-candle execution that could not have occurred.
- Profit disappears after delaying entry by one bar.
- Profit is concentrated in one asset, one month, one market event, or very few trades.
- Adjacent, economically sensible parameter values perform materially worse.
- Performance disappears out of sample or under doubled costs.
- It fails to outperform a materially simpler baseline.
- Maximum drawdown is unacceptable relative to expected return.
- It only works because the market generally rose.
- The sample is too small to support a useful conclusion.

A rejection is a successful result when it prevents capital or research time being allocated to a weak hypothesis. A rejected experiment may justify a narrower follow-up hypothesis.

## Evidence and verdict ladder

- **REJECTED:** a core falsification criterion failed.
- **INCONCLUSIVE:** evidence is mixed, underpowered, or materially fragile.
- **RESEARCH CANDIDATE:** net evidence is positive enough to justify another historical test, but not paper trading.
- **PAPER-TRADING CANDIDATE:** requires positive after-cost and out-of-sample results, nearby-parameter stability, higher-cost survival, adequate trade count, acceptable drawdown, no material concentration, a plausible mechanism, and no known leakage.

No experiment in this repository is live-trading authorization or investment advice.
