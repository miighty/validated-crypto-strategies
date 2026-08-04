# TradingView Replication Records

Python is the validation authority. TradingView is a supplementary review and operational handoff surface, not the source of parameter selection or a completion gate. The corresponding Pine files are in `pine/` and are designed to run on the current chart symbol.

## Required record per run

- Experiment ID and Pine file commit/hash.
- TradingView chart symbol, exchange, and four-hour timeframe.
- Research window: development 2016–2020, validation 2020–2024, or forward 2024–2026.
- Every non-default Pine input.
- Strategy Properties: initial capital, order size, commission, slippage in ticks, margin, and recalculation settings.
- Actual first and last bar available to Strategy Tester.
- Net profit, percent return, maximum drawdown, total trades, profitable trades, profit factor, and any warning shown by TradingView.
- Reconciliation status against the Python run and an explanation of material differences.

## Current status

| Experiment | Pine strategy | BTCUSDT | ETHUSDT | SOLUSDT | Status |
| --- | --- | --- | --- | --- | --- |
| EXP-2026-08-04-RSI-001 | `pine/rsi_mean_reversion_strategy.pine` | Forward −16.10% | Forward −60.04% | Forward −40.51% | Compiled and forward-tested on all default markets; rejected consistently |
| EXP-2026-08-04-BO-001 | `pine/breakout_acceptance_rejection_strategy.pine` | Forward +1.49% | Forward +91.07% | Forward +21.27% | Compiled and forward-tested on all default markets; selected candidate positive on each |

The TradingView account is on the Basic plan. TradingView explicitly reported that it can calculate only with data loaded on the chart; on the four-hour charts used here, the available tester history began on 2024-01-01. Older TradingView windows are therefore deferred. The Python engine has completed all three frozen windows independently and determines the research verdict.

TradingView runs use 5 bp commission per side and zero slippage ticks. The Python runs additionally charge 5 bp proportional slippage per side. Pine's built-in slippage setting is denominated in chart ticks, not basis points, so the records deliberately disclose the difference instead of claiming exact numerical parity.

No script or TradingView idea has been published.
