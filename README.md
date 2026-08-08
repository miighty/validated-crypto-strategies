# Crypto Regime Strategy Validation

A public, reproducible research package that states exactly which requested crypto strategies received a completed historical backtest, preserves every real exchange input used, and refuses to label unsupported simulations as validation.

## Minimum viable edge-research loop

The repository now also contains a smaller falsification-first workflow for moving from a frozen hypothesis to Python backtest, hostile robustness checks, Pine Script replication, and a conservative verdict. Its governing requirements are in [docs/research_brief.md](docs/research_brief.md) and [docs/research_constitution.md](docs/research_constitution.md).

Current completed experiments:

- **RSI oversold mean reversion — REJECTED.** The frozen RSI(14) < 30, four-bar rule lost 92.5% over the available full sample and 48.0% in the 2024–2026 forward window after costs. See [reports/EXP-2026-08-04-RSI-001.md](reports/EXP-2026-08-04-RSI-001.md).
- **Breakout family — RESEARCH CANDIDATE.** Pre-2024 selection chose the simpler 50-bar immediate long breakout, not acceptance or rejection. It returned 28.1% in the Python 2024–2026 forward window and survived the declared robustness checks. The corresponding Pine strategy is ready for TradingView review and adjustment, but this is not a paper- or live-trading approval. See [reports/EXP-2026-08-04-BO-001.md](reports/EXP-2026-08-04-BO-001.md).
- **Crypto equities after wild BTC moves — REACTION CONFIRMED.** BTC strongly led the opening gap, including 0.932 correlation on 25 wild overnight sessions. The original residual P&L test was later withdrawn because its observation and fill windows overlapped; the corrected executable strategy is reported separately. The dedicated weekend sample remained underpowered. See [reports/EXP-2026-08-04-CROSS-ASSET-001.md](reports/EXP-2026-08-04-CROSS-ASSET-001.md).
- **BTC-to-crypto-equity opening-gap strategy — REJECTED FOR DEPLOYMENT.** The formally selected BTC-continuation rule lost 32.68% over five years. A corrected 09:40-entry, long-only residual-continuation alternative returned 56.15%, but failed the frozen independence, event-concentration, and threshold-stability gates. See [reports/EXP-2026-08-05-CROSS-ASSET-STRAT-001.md](reports/EXP-2026-08-05-CROSS-ASSET-STRAT-001.md).
- **MSTR opening fade after BTC sell-offs — REJECTED FOR DEPLOYMENT.** Buying MSTR at the opening print after a pre-open BTC crash lost money for each of the declared 5-, 10-, and 15-minute exits in 2021–2023. The later positive observations are too few and were not used to select a rule. See [reports/EXP-2026-08-05-MSTR-OPEN-FADE-001.md](reports/EXP-2026-08-05-MSTR-OPEN-FADE-001.md).
- **BTC 30% / 72h drawdown reserve deployment — REJECTED.** The preregistered crash-buy rule never triggered once in the 2021–2026 Binance BTC sample, and nearby looser variants still finished with less BTC than simple daily and weekly DCA baselines. See [docs/BTC_DRAWDOWN_DCA_VALIDATION.md](docs/BTC_DRAWDOWN_DCA_VALIDATION.md).
- **BTC ETF odds -> BTC swing — REJECTED.** Real BTC ETF approval-odds shocks generated only three trades and still finished behind both daily and weekly BTC DCA over the active market window. See [docs/BTC_ETF_VALIDATION.md](docs/BTC_ETF_VALIDATION.md).
- **BTC extreme-move edge suite — NO VALIDATED EDGE.** Across 180 rerunnable BTC crash/rally variants, none cleared the untouched-test, bootstrap, and matched-random gates; the best-looking crash-buy variants remained underpowered. See [docs/EDGE_VALIDATION.md](docs/EDGE_VALIDATION.md).

The current plain-English decision summary, including completed, rejected, preliminary and data-gated work, is [reports/STRATEGY-EVIDENCE-AUDIT-2026-08-06.md](reports/STRATEGY-EVIDENCE-AUDIT-2026-08-06.md).

The frozen methodology for crypto-equity weekend/overnight reactions, BTC lead–lag, and liquidation increment studies is in [docs/cross_asset_validation_plan.md](docs/cross_asset_validation_plan.md). Studies 6 and 7 are complete. Study 8 remains data-gated because the current CoinGlass entitlement does not include aggregate liquidation history.

The default research windows are development 2016–2020, validation 2020–2024, and untouched forward test 2024–2026. Reports use actual exchange coverage: Binance BTCUSDT and ETHUSDT begin in August 2017 and SOLUSDT in August 2020, so unavailable history is never fabricated.

### Install and run

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/edge-research download --config configs/data.yaml
.venv/bin/edge-research run --config configs/rsi_mean_reversion.yaml
.venv/bin/edge-research run --config configs/breakout_acceptance.yaml
.venv/bin/edge-research verify
.venv/bin/pytest -q
```

After acquiring the licensed Databento cache, reproduce studies 6 and 7 with:

```bash
.venv/bin/edge-research cross-asset-run

# Test the separately frozen MSTR 09:30 opening-fade hypothesis
.venv/bin/edge-research mstr-open-fade
```

The five-year executable strategy specification is frozen in [docs/cross_asset_strategy_spec.md](docs/cross_asset_strategy_spec.md). With the local five-year cache present, reproduce its validation suite with `edge-research cross-asset-strategy`.

The profitable residual-continuation alternative now has a separately pre-registered,
forward-only paper ledger beginning 5 August 2026. It cannot submit orders, rejects parameter
changes, and will not request review before 30 new wild-event sessions. See
[docs/cross_asset_forward_test.md](docs/cross_asset_forward_test.md). Once the licensed equity
panel and public BTC file contain a finalized session, append it with
`edge-research cross-asset-forward --through YYYY-MM-DD`.

Run a manually chosen Binance universe after downloading that same snapshot:

```bash
.venv/bin/edge-research download --config configs/data.yaml --symbols SOL ETC
.venv/bin/edge-research run --config configs/breakout_acceptance.yaml --symbols SOL ETC
```

Bare tickers default to USDT, so `SOL ETC`, `SOLUSDT ETCUSDT`, and `SOL/USDT ETC/USDT` are equivalent. Comma-separated input is also accepted. Adding a manually selected market updates that market in the data catalog without deleting previously downloaded symbols. A manual experiment receives a stable `-MANUAL-<symbols>` report ID, so it never overwrites the canonical BTC/ETH/SOL evidence.

Python is the validation authority. The chart-agnostic, adjustable handoff strategies are [pine/rsi_mean_reversion_strategy.pine](pine/rsi_mean_reversion_strategy.pine) and [pine/breakout_acceptance_rejection_strategy.pine](pine/breakout_acceptance_rejection_strategy.pine). Choose any TradingView chart symbol and the four-hour timeframe, select a frozen or custom window in Inputs, and record chart-specific tick slippage in Strategy Properties. TradingView history availability is supplementary rather than a completion gate. The scripts are private source artifacts until you explicitly choose to publish or share them.

The forward crypto-equity experiment also has a private supplementary Pine v6 companion at
[pine/btc_crypto_equity_residual_continuation.pine](pine/btc_crypto_equity_residual_continuation.pine).
It runs one frozen-universe US equity at a time on a standard one-minute chart with extended
hours; it cannot replace the Python portfolio ledger.

The completed requirement-by-requirement audit is recorded in [docs/completion_audit.md](docs/completion_audit.md).

## Evidence boundary

- **Data:** finalized public Binance spot OHLCV and USD-M perpetual funding observations, pinned from 2018-01-01 through 2026-07-28 (exclusive), subject to actual listing dates.
- **Costs:** 0.10% fee plus 0.05% slippage for each one-way position change.
- **Timing:** indicators use finalized bars and positions execute no earlier than the next bar open.
- **Artifacts:** compressed source CSVs, SHA-256 manifest, regime labels, trades, returns, metrics, charts, and a generated report are committed.
- **Claim:** `historical_backtest_completed` means the documented implementation ran on the committed historical sample. It does **not** mean proven edge, out-of-sample validation, investment advice, or readiness for paper/live execution.

See [REPORT.md](REPORT.md) for the result tables and [docs/METHODOLOGY.md](docs/METHODOLOGY.md) for exact strategy and validation rules.

## Strategies run and historical P&L

The figures below use each strategy's committed daily return series to build a hypothetical **$10,000 equal-weight portfolio across the ten requested assets**. P&L is ending equity minus $10,000 after the documented fees and slippage. These are in-sample historical research results, not forecasts or evidence of a durable trading edge.

| Strategy | What was tested | Timeframe | Result status | Ending equity | Net P&L | Total return | Max drawdown |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| Trend following | EMA(20) cross in the EMA(50) direction with a 2×ATR trailing exit | 1d | Completed | $38,300.47 | +$28,300.47 | +283.00% | 58.35% |
| Mean reversion | Bollinger Band touch plus RSI extreme, middle-band exit and 1.5×ATR stop | 4h | Completed | $109.98 | -$9,890.02 | -98.90% | 99.10% |
| Cross-sectional momentum | Weekly long top three and short bottom three by 20-day return | 1d | Completed | $11,505.22 | +$1,505.22 | +15.05% | 8.13% |
| Breakout | Prior 20-bar high/low break with 1.5× volume confirmation and 2×ATR trail | 4h | Completed | $13,956.25 | +$3,956.25 | +39.56% | 61.25% |
| Grid | Twenty 2% levels around the prior finalized daily close, capped at ±1 exposure | 1h | Completed | $302.85 | -$9,697.15 | -96.97% | 97.23% |
| DCA | Invest $100 weekly from each asset run's fixed $10,000 cash balance until depleted | 1d | Completed | $238,963.48 | +$228,963.48 | +2,289.63% | 78.33% |
| Funding arbitrage | Delta-neutral spot/perpetual position when real absolute funding exceeds 0.05% | Funding events | Preliminary backtest completed | $6,891.51 | -$3,108.49 | -31.08% | 31.50% |
| Statistical arbitrage | Five requested pairs using a 30-day log-ratio z-score with ±2 entry | 4h | Completed | $3,782.96 | -$6,217.04 | -62.17% | 63.02% |
| Market making | Requested 0.3% two-sided spread and inventory rules | Order-book data required | **Not run / not validated** | — | — | — | — |
| Contrarian | RSI below 20/above 80 with 2× volume confirmation and 3×ATR stop | 1d | Completed | $4,174.81 | -$5,825.19 | -58.25% | 64.96% |

No requested strategy is absent from the report. Market making is the only strategy without a backtest result or P&L because the dataset contains candles rather than historical order-book events and executable fills. Funding arbitrage has a result, but it remains preliminary because borrow costs, basis movement, collateral yield, margin and liquidation are not modeled.

The figures can be reproduced from [results/strategy_daily_returns.csv](results/strategy_daily_returns.csv). Per-asset/per-regime metrics are in [results/all_metrics.csv](results/all_metrics.csv), and the evidence status for every requested strategy is in [results/validation_status.csv](results/validation_status.csv).

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
