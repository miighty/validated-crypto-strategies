# Crypto Regime Strategy Validation

A public, reproducible research package that states exactly which requested crypto strategies received a completed historical backtest, preserves every real exchange input used, and refuses to label unsupported simulations as validation.

## Evidence boundary

- **Data:** finalized public Binance spot OHLCV and USD-M perpetual funding observations, pinned from 2018-01-01 through 2026-07-28 (exclusive), subject to actual listing dates.
- **Costs:** 0.10% fee plus 0.05% slippage for each one-way position change.
- **Timing:** indicators use finalized bars and positions execute no earlier than the next bar open.
- **Artifacts:** compressed source CSVs, SHA-256 manifest, regime labels, trades, returns, metrics, charts, and a generated report are committed.
- **Claim:** `historical_backtest_completed` means the documented implementation ran on the committed historical sample. It does **not** mean proven edge, out-of-sample validation, investment advice, or readiness for paper/live execution.

See [REPORT.md](REPORT.md) for the result tables and [docs/METHODOLOGY.md](docs/METHODOLOGY.md) for exact strategy and validation rules.

## Quick start

```bash
uv sync --extra dev
uv run crypto-regime-backtest verify
uv run pytest -q
```

Recompute results from the committed data:

```bash
uv run crypto-regime-backtest run
uv run crypto-regime-backtest report
```

Refresh from the public exchange only when intentionally creating a new snapshot:

```bash
uv run crypto-regime-backtest fetch --refresh
```

Refreshing changes the evidence and invalidates the committed checksums until the pipeline and report are rerun.

## Repository map

```text
data/raw/                 finalized OHLCV inputs (.csv.gz)
data/funding/             real historical funding inputs (.csv.gz)
data/manifest.json        source window, row counts, and SHA-256 checksums
data/provenance.csv       human-readable data provenance
regimes/                  daily regime classifications and indicators
results/trades/           trade/event ledgers
results/returns/          per-strategy, per-asset return and equity series
results/metrics/          per-strategy, per-asset, per-regime JSON metrics
charts/                   generated report figures
src/                      fetch, indicator, strategy, backtest, and report code
tests/                    timing, cost, classification, and data-invariant tests
```

## Safety

The project contains no exchange keys, wallets, account identifiers, order placement, scheduler, deployment configuration, or live/paper trading integration. Public market data is fetched from unauthenticated endpoints only. See [SECURITY.md](SECURITY.md).
