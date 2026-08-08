# Crypto Edge Validation Suite

Run the currently executable BTC studies with:

```bash
uv run crypto-regime-backtest validate-edge
```

## Latest finding

- **Validated edge variants:** **0**
- **Failed variants:** **121**
- **Insufficient-data variants:** **48**
- **Best-looking cluster:** BTC **48h crash-buy** variants around **10% to 15% drawdowns** and **24h to 168h holds** sometimes showed positive full-sample expectancy, but they **did not clear the untouched-test event-count gate** and therefore remain rejected.
- **Data-gated studies:** crypto-stock lag, liquidation-conditioned lag, and Strategy Inc. event studies remain fail-closed until real point-in-time source files are supplied.

Artifacts from the latest run:

- `results/edge_validation/runs/run-20260808T021926Z/RANKED_REPORT.md`
- `results/edge_validation/runs/run-20260808T021926Z/variant_results.csv`
- `results/edge_validation/runs/run-20260808T021926Z/event_ledger.csv`
- `results/edge_validation/runs/run-20260808T021926Z/dca_benchmarks.csv`

The command only consumes committed BTC hourly OHLCV plus completed daily regime labels. A signal is known at a completed hourly close and enters at the following hourly open. Each event pays the configured one-way fee/slippage at entry and exit. Events are non-overlapping for their selected holding period. Results with fewer than 20 events are labelled `insufficient_data`; they are never promoted to a pass.

The suite writes a fresh immutable-style directory under `results/edge_validation/runs/` containing `variant_results.csv`, `event_ledger.csv`, `dca_benchmarks.csv`, and `RANKED_REPORT.md`. It makes no live/paper orders and does not fetch unpinned event data.

## Point-in-time input contracts

Place real, timestamped source files in `data/edge_validation/`. All timestamps must be UTC and must reflect when the information became available, not merely the period it describes.

| Study | Required files | Minimum columns |
| --- | --- | --- |
| Crypto-stock overnight lag | `equity_bars.csv.gz`, `index_futures_bars.csv.gz` | `timestamp,symbol,open,high,low,close,volume,session` |
| Liquidation-conditioned lag | above plus `liquidations.csv.gz`, `open_interest.csv.gz`, `funding.csv.gz` | `timestamp,symbol,long_liquidations,short_liquidations`; and `timestamp,symbol,open_interest` / `funding_rate` |
| Strategy Inc. transaction period | `strategy_inc_transactions.csv` | `transaction_start,transaction_end,btc_amount,dollar_value,side,source_url` |
| Strategy Inc. disclosure event | `strategy_inc_disclosures.csv`, `mstr_bars.csv.gz` | `announcement_timestamp,filing_timestamp,side,expected_size,surprise,source_url` plus OHLCV |

No announcement is treated as the transaction timestamp. Crypto-stock results count only post-open, or separately labelled realistically accessible premarket, returns. The future adapters must estimate expected gaps using point-in-time BTC/ETH, stock beta, and index-futures inputs before computing residual gaps.

## Decision gates

An edge passes only if the untouched chronological test set has at least 20 independent events, positive net expectancy after costs, a positive 95% bootstrap lower bound, and a higher mean than month/volatility-matched random entries. Every other outcome is `fail` or `insufficient_data`. Parameter grids are reported as sensitivity analysis, never selected after seeing the test period.
