# Positive funding panel validation

Run artifact: `results/funding_positive_panel/runs/run-20260808T070137Z/REPORT.md`

## Key findings

- **Primary rule tested:** across real Binance funding for **BTC / ETH / SOL / XRP / BNB / ADA / DOGE / AVAX / LINK**, if one or more completed 8h funding prints are **>= +5 bps**, select the **single most positive** asset, buy spot at the **next hourly open**, hold **8h**, then wait **24h** before the next trade.
- **Sample:** `2021-01-01` through the pinned final window using only real Binance hourly spot and real Binance USD-M funding history.
- **Benchmarks:** same fixed **$10,000** reserve released as equal daily contributions, compared against **daily BTC, ETH, SOL, and XRP DCA** plus a **daily equal-weight nine-asset universe DCA**.

## Result table

| Strategy | Final USD | Trades | Avg trade | Win rate | Verdict |
|---|---:|---:|---:|---:|---|
| Daily BTC DCA | 15105.45 | 2034 | n/a | n/a | Baseline |
| Daily ETH DCA | 8602.24 | 2034 | n/a | n/a | Baseline |
| Daily SOL DCA | 19664.59 | 2034 | n/a | n/a | Baseline |
| Daily XRP DCA | 15583.79 | 2034 | n/a | n/a | Baseline |
| Daily equal-weight 9-asset DCA | 10757.07 | 2034 | n/a | n/a | Baseline |
| Random matched-schedule asset baseline | 8221.13 | 124 | -0.01% | 44.4% | Baseline |
| Positive funding persistence panel | 9586.24 | 124 | 0.52% | 45.2% | **Rejected** |

## Honest conclusion

> **Rejected.** Extreme positive funding did **not** produce a usable long-spot persistence edge after costs. The rule lost money overall, finished far behind the required DCA baselines, and produced **zero trades in the 2025+ holdout** because Binance funding never again reached the preregistered +5 bps trigger in this panel.

## Decisive checks

- **Doubled-cost check:** terminal value fell to **$8929.23**.
- **Best-trade exclusion:** terminal value stayed weak at **$9529.94**.
- **Sensitivity:** every nearby threshold/hold variant stayed below breakeven; the least-bad tested variant was **+10 bps / 24h hold** at **$9666.18**.

## Files

- `results/funding_positive_panel/runs/run-20260808T070137Z/strategy_summary.csv`
- `results/funding_positive_panel/runs/run-20260808T070137Z/trade_log.csv`
- `results/funding_positive_panel/runs/run-20260808T070137Z/signal_panel.csv`
- `results/funding_positive_panel/runs/run-20260808T070137Z/sensitivity_checks.csv`
- `results/funding_positive_panel/runs/run-20260808T070137Z/hostile_checks.csv`
