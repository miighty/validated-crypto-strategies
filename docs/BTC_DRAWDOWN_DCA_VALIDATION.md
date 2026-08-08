# BTC drawdown reserve deployment validation

Run:

```bash
uv run crypto-regime-backtest validate-btc-drawdown-dca
```

## Latest finding

- **Primary rule tested:** after a completed **30% BTC close-to-close drawdown over 72h**, buy BTC at the **next hourly open** with the **entire accrued reserve**; then wait for the next qualifying event.
- **Benchmarks:** same fixed $10,000 reserve released as equal daily contributions and spent by **daily BTC DCA** or **weekly Monday BTC DCA**.
- **Costs:** **15 bps per buy**.
- **Sample:** Binance spot BTCUSDT 1h, **2021-01-01 through 2026-07-27**.

## Verdict

- The preregistered **30% / 72h** rule was **rejected**.
- It triggered **0 times** in the full 2021-2026 sample, so it never deployed capital.
- Daily DCA finished at **$15,105.45** and weekly Monday DCA at **$15,095.72**.
- Nearby variants that did trigger (mostly **25%** drawdown rules, and **30% over 96h**) still ended with **less BTC than both DCA baselines**.

## Current blocker / interpretation

This is not a hidden edge that narrowly missed. The exact crash-buy rule is simply too sparse for post-2020 BTC, and loosening it does not beat the simpler passive baselines after costs.

## Artifacts

- `results/btc_drawdown_dca/runs/run-20260808T022806Z/REPORT.md`
- `results/btc_drawdown_dca/runs/run-20260808T022806Z/strategy_summary.csv`
- `results/btc_drawdown_dca/runs/run-20260808T022806Z/sensitivity_checks.csv`
- `results/btc_drawdown_dca/runs/run-20260808T022806Z/hostile_checks.csv`
