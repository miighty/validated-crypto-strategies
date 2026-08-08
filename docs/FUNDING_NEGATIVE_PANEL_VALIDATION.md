# Negative funding panel validation

Run artifact: `results/funding_negative_panel/runs/run-20260808T055210Z/REPORT.md`

## Key findings

- **Primary rule tested:** across real Binance funding for **BTC / ETH / SOL / XRP / BNB / ADA / DOGE / AVAX / LINK**, if one or more completed 8h funding prints are **<= -5 bps**, select the **single most negative** asset, buy spot at the **next hourly open**, hold **24h**, then wait **24h** before the next trade.
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
| Random matched-schedule asset baseline | 7426.74 | 113 | -0.05% | 53.1% | Baseline |
| Negative funding rebound panel | 6747.34 | 113 | 0.31% | 45.1% | **Rejected** |

## Honest conclusion

> **Rejected.** The simple negative-funding rebound rule generated plenty of trades, but it still finished badly behind the required DCA benchmarks and even trailed the matched-schedule random-asset baseline.

## Decisive checks

- **Doubled-cost check:** terminal value fell to **$6172.73**.
- **Best-trade exclusion:** terminal value stayed weak at **$6731.44**.
- **Sensitivity:** the least-bad nearby variant was **-5 bps / 8h hold**, but it still lost money at **$9661.32** and remained behind the required DCA baselines.

## Files

- `results/funding_negative_panel/runs/run-20260808T055210Z/strategy_summary.csv`
- `results/funding_negative_panel/runs/run-20260808T055210Z/trade_log.csv`
- `results/funding_negative_panel/runs/run-20260808T055210Z/signal_panel.csv`
- `results/funding_negative_panel/runs/run-20260808T055210Z/sensitivity_checks.csv`
- `results/funding_negative_panel/runs/run-20260808T055210Z/hostile_checks.csv`
