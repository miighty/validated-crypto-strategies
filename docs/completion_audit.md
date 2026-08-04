# Minimum Viable Edge Research System — Completion Audit

Audited on 2026-08-04 against the research goal and the later Pine/manual-universe requirements. Python is the validation authority; TradingView is a downstream review and operational handoff, not a completion gate. “Complete” below means the current repository contains direct, reproducible evidence; it does not mean a trading edge has been approved for deployment.

| Requirement | Status | Authoritative evidence |
| --- | --- | --- |
| Trustworthy BTC/ETH/SOL four-hour data | Complete | `data/processed/quality_report.json`, Parquet snapshots, OHLCV validation in `src/edge_research/data.py`, and `edge-research verify` |
| Reusable next-bar long/short backtester | Complete | `src/edge_research/engine.py` plus manually calculable long/short, stop, gap, and timing tests |
| Realistic disclosed costs | Complete | Configured 5 bp fee and 5 bp proportional slippage per side; doubled-cost hostile tests; reports disclose TradingView’s tick-slippage difference |
| Weak RSI experiment and baselines | Complete and rejected | `reports/EXP-2026-08-04-RSI-001.md`, machine results, trades, charts, random and simple-rule controls |
| Credible breakout-family experiment | Complete as research candidate | `reports/EXP-2026-08-04-BO-001.md`, pre-2024 selection, sealed forward test, family comparisons, and hostile checks |
| Hostile robustness checks | Complete | Doubled costs, delayed entries, symbol removal, best-year removal, nearby lookbacks, holding horizons, sizing, regimes, and baselines in the generated reports |
| Automatic Markdown reports and permanent registry | Complete | `src/edge_research/reporting.py`, generated reports, summaries, assets, and `docs/experiment_registry.md` |
| Documented next tests | Complete | `docs/next_hypotheses.md` and each report’s next justified experiment |
| Adjustable Pine counterpart for each experiment family | Complete | Pine v6 scripts in `pine/`; contract tests enforce next-bar settings, frozen windows, and selected breakout defaults |
| Manual coin selection such as SOL and ETC | Complete | Bare tickers, comma-separated values, explicit slash pairs, and exchange symbols normalize through `normalize_symbols`; manual reports receive separate stable IDs; a real SOL-only run produced `EXP-2026-08-04-RSI-001-MANUAL-SOLUSDT` without replacing the canonical report |
| Supplementary TradingView forward replication on BTC/ETH/SOL | Complete | Structured records in `reports/tradingview/` and visible Strategy Tester results for both strategies on all three markets |
| TradingView 2020–2024 and 2016–2020 replication | Deferred outside validation scope | Python completed both frozen windows. TradingView Basic rejects Entire History/Custom Date Range and exposes no usable pre-2024 four-hour bars, but this does not block the research verdict or Pine handoff. |
| Publication control | Complete | Every TradingView record has `published: false`; no script or idea was published |

## Completion conclusion

All in-scope research-system requirements are complete. The Python source-of-truth results cover every frozen window and support the recorded verdicts. Historical TradingView replication may be added later if Deep Backtesting/history access becomes available, without reopening or changing the Python validation decision.
