# BTC Shock -> Alt Underreaction Validation

Run:

```bash
uv run crypto-regime-backtest validate-btc-alt-response
```

## Key findings

- **Primary rule tested:** if BTC rises at least **3% over the prior 4 completed hourly bars** and the target alt gained at most **60% of that move**, enter **long ETH / SOL / XRP** at the **next hourly open**, hold **72h**, then return to cash.
- **Costs:** **15 bps per side**.
- **Benchmarks:** same released-capital schedule versus **daily** and **weekly Monday DCA** for the traded alt, plus passive DCA reference rows for **BTC, ETH, SOL, XRP**.
- **Sample:** pinned Binance spot **1h** candles from **2021-01-01** through the repo cutoff.

## Verdict

| Asset | Terminal value | Trades | Verdict | Why |
| --- | ---: | ---: | --- | --- |
| ETH | 11995.18 | 54 | Rejected | Beat ETH DCA, but only **1 holdout trade** after 2025-01-01. |
| SOL | 10696.83 | 66 | Rejected | Lag-filter version underperformed SOL DCA and had only **2 holdout trades**. |
| XRP | 22597.97 | 106 | Rejected | Strong total P&L, but only **5 holdout trades** and negative holdout mean trade return. |

## Decisive blockers

1. **Holdout sample was far too small** on every asset, so the strategy does not clear the predeclared out-of-sample gate.
2. The lag filter **did not dominate simpler baselines** consistently:
   - ETH: unfiltered BTC-shock continuation had higher mean trade return than the lag-filtered version.
   - SOL: both unfiltered BTC-shock continuation and same-asset momentum beat the lag-filtered version.
   - XRP: same-asset momentum also exceeded the lag-filtered mean trade return.
3. Despite attractive in-sample / full-sample totals, the evidence remains **exploratory only**.

## Artifact

Latest completed run in this repo:

- `results/btc_alt_response/runs/run-20260808T014715Z/`
