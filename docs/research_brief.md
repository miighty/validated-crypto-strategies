# Minimum Viable Quantitative Edge Research System — Canonical Brief

## Objective

Build the shortest trustworthy path from **hypothesis → frozen specification → Python backtest → robustness checks → rejection or promotion decision → optional Pine/TradingView handoff**.

This is a research system, not live execution, investment advice, a dashboard, or cloud infrastructure. Every result is presumed false until it survives realistic costs, next-bar execution, simple baselines, independent time windows, nearby parameters, and concentration checks.

## Deliverables

1. A reproducible Python research repository using real, finalized OHLCV data.
2. A reusable long/short/flat backtester with next-open entries, fees, slippage, stops, time exits, sizing, trade ledgers, and portfolio equity.
3. Adjustable YAML experiment configurations.
4. Manual symbol selection from the command line, with BTC/USDT, ETH/USDT, and SOL/USDT as defaults. Examples such as ETC/USDT are supported when the selected exchange has data.
5. A deliberately weak RSI oversold mean-reversion experiment and its baselines.
6. A credible breakout acceptance/rejection family and its baselines.
7. A Pine Script strategy corresponding to every experiment family, with user-adjustable parameters and dates.
8. A reviewable Pine/TradingView handoff for promoted strategies. TradingView replication is supplementary and is not a validation or completion gate.
9. Automatic Markdown reports, charts, an experiment registry, and a prioritized next-hypothesis backlog.
10. Failed experiments preserved with explicit rejection reasons.

## Frozen research windows

The default windows are defined before results are inspected:

- **Development:** 2016-01-01 through 2019-12-31.
- **Validation:** 2020-01-01 through 2023-12-31.
- **Forward/untouched test:** 2024-01-01 through the latest complete candle available in 2026.

Each report must state the *actual* coverage. Binance spot BTC/USDT and ETH/USDT do not reach January 2016, and SOL/USDT did not exist in 2016; unavailable pre-listing history must remain missing and must never be fabricated. A window with inadequate observations is labelled unavailable or underpowered rather than silently shortened.

The development and validation windows may select a predeclared candidate. The 2024–2026 window must not influence parameter selection and is inspected only after that selection is frozen.

## Adjustable universe and parameters

The default data configuration lists BTCUSDT, ETHUSDT, and SOLUSDT, but download and run commands must accept explicit symbol overrides such as:

```bash
edge-research download --config configs/data.yaml --symbols SOL ETC
edge-research run --config configs/rsi_mean_reversion.yaml --symbols SOL ETC
```

Bare tickers default to the configured USDT quote; explicit forms such as `SOLUSDT`, `SOL/USDT`, and non-USDT pairs remain available. Manual downloads upsert the requested markets without deleting previously downloaded symbols. Manual experiment reports receive stable universe-specific IDs and must not overwrite the frozen default-universe artifacts. Strategy thresholds, lookbacks, holding periods, stops, costs, sizing, dates, and breakout variants remain editable in YAML and in the corresponding Pine inputs. Parameter testing stays deliberately small and economically interpretable.

## Pine and TradingView handoff contract

- Python is the auditable validation source of truth and produces the frozen candidate and verdict.
- Pine scripts use the current TradingView chart symbol, so the researcher can manually test any available coin or pair.
- Signals use completed candles and orders are submitted no earlier than the following bar.
- TradingView is used after Python validation for manual review, parameter adjustment, and eventual operational use.
- When a TradingView run is recorded, its commission, slippage, date range, position sizing, timeframe, and non-default inputs must be preserved with the result.
- Available Strategy Tester outputs may be stored in `reports/tradingview/`, but missing historical platform coverage does not invalidate a completed Python experiment.
- Differences between Python and TradingView are investigated, not averaged away. Exchange feed, timezone, order-fill, stop-order, tick-size, and commission semantics remain expected reconciliation points.
- Pine scripts are stored in `pine/` for the user to review and share later. Do not publish a TradingView idea or public script without a separate explicit instruction from the user.

## Research constitution

Every experiment follows [research_constitution.md](research_constitution.md), including required hypothesis fields and default rejection criteria. Important financial logic requires unit tests and at least one manually calculable synthetic trade path.

## Today’s experiment specifications

### RSI oversold mean reversion

- RSI(14) below 30 at a completed four-hour close.
- Long entry at the next open.
- Exit after four bars or after RSI closes above 50, whichever triggers first.
- Two-ATR protective stop when cleanly modelled.
- Small matrix: thresholds 25/30/35 and holding periods 2/4/8.
- Baselines: repeated fixed-seed random entries, large negative candle, buy and hold, and a simple trend rule.
- Attempt rejection through costs, one-extra-bar delay, asset/time concentration, adjacent parameters, and forward-window performance.

### Breakout acceptance and rejection

- Previous rolling high excludes the current candle.
- Lookbacks 20 and 50; ATR(14).
- Compare immediate breakout long, accepted breakout long, and failed-breakout short.
- Acceptance requires a later completed candle to remain above the old breakout level; rejection requires a close back below it within the declared window.
- Entry occurs at the following open; exits use the old level, ATR stop, and fixed horizon.
- Limited parameter tests: lookback 20/50, window 1/2, buffer 0/0.1 ATR, plus a small horizon sensitivity.
- The selected development/validation candidate receives doubled-cost, delayed-entry, per-asset, remove-best-asset/year, regime, sizing, nearby-lookback, concentration, and largest-trade reviews before the forward window is opened.

## Verdicts

Available verdicts are **REJECTED**, **INCONCLUSIVE**, **RESEARCH CANDIDATE**, and **PAPER-TRADING CANDIDATE**. Historical profitability alone never qualifies a strategy for paper trading.
