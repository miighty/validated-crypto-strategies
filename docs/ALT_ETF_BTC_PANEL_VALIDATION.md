# Alt ETF Odds Family -> Alt/BTC Spread Validation

Run artifact: `results/alt_etf_btc_panel/runs/run-20260808T050754Z/REPORT.md`

## Key findings

- **Primary rule tested:** across the real Polymarket **ETH / SOL / XRP spot-ETF approval** markets, trigger when YES odds jump by at least **10 points over 24h** and remain at or above **55%**; enter **long the alt / short BTC** at the next hourly open, hold **72h**, then exit.
- **Capital rule:** one global sleeve, **non-overlapping positions**, plus a **24h cooldown** after exit.
- **Benchmarks:** same fixed **$10,000** reserve released as equal daily contributions from **2024-01-01** onward, compared against **daily BTC, ETH, SOL, and XRP DCA** plus a **daily equal-weight ETH/SOL/XRP basket DCA**.

## Result table

| Strategy | Final USD | Trades | Avg trade | Win rate | Verdict |
|---|---:|---:|---:|---:|---|
| Daily BTC DCA | 8380.74 | 939 | n/a | n/a | Baseline |
| Daily ETH DCA | 7093.32 | 939 | n/a | n/a | Baseline |
| Daily SOL DCA | 5633.59 | 939 | n/a | n/a | Baseline |
| Daily XRP DCA | 10337.67 | 939 | n/a | n/a | Baseline |
| Daily equal-weight alt basket | 7688.19 | 2817 | n/a | n/a | Baseline |
| Alt ETF odds family -> alt/BTC spread | 9209.93 | 16 | -0.60% | 44% | Rejected |

## Honest conclusion

> **Rejected.** Extending the ETH ETF idea into a pooled ETH/SOL/XRP analogue family improved sample size to **16 trades**, but the unified rule still failed the decisive benchmark test: it finished **behind XRP DCA**.

## Decisive checks

- **Doubled-cost check:** final USD fell to **8879.59**.
- **Best-trade exclusion:** removing the best trade cut final USD to **9008.39**.
- **Interpretation:** the analogue-family extension adds real event count, but it does **not** justify upgrading the standalone ETH ETF spread from **promising but inconclusive** to validated edge.

## Files

- `results/alt_etf_btc_panel/runs/run-20260808T050754Z/strategy_summary.csv`
- `results/alt_etf_btc_panel/runs/run-20260808T050754Z/trade_log.csv`
- `results/alt_etf_btc_panel/runs/run-20260808T050754Z/signal_panel.csv`
- `results/alt_etf_btc_panel/runs/run-20260808T050754Z/sensitivity_checks.csv`
- `results/alt_etf_btc_panel/runs/run-20260808T050754Z/hostile_checks.csv`
