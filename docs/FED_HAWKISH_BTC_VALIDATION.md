# Falling Fed-cut odds -> BTC swing validation

Run artifact: `results/fed_hawkish_btc/runs/run-20260808T082630Z/REPORT.md`

## Key findings

- **Primary rule tested:** across the real Polymarket **Fed-cut family** (March / May / June / September cut-deadline markets plus the `6+ cuts in 2024` market), if YES odds fall by at least **12 points over 24h** and remain at or below **45%**, enter **spot BTC long** at the **next hourly open**, hold **72h**, then exit and wait **24h** before the next entry.
- **Sample:** `2023-12-18` through the final overlapping Fed-market observation in the pinned repo, using only real Polymarket hourly YES odds plus real Binance BTC/ETH/SOL/XRP hourly spot candles.
- **Benchmarks:** same fixed **$10,000** reserve released as equal daily contributions, compared against **daily BTC, ETH, SOL, and XRP DCA**, plus **same-schedule always-long equal-weight** and **random-asset schedule** baselines.

## Result table

| Strategy | Final USD | Trades | Avg trade | Win rate | Verdict |
|---|---:|---:|---:|---:|---|
| Daily BTC DCA | 17123.40 | 367 | n/a | n/a | Baseline |
| Daily ETH DCA | 13301.61 | 367 | n/a | n/a | Baseline |
| Daily SOL DCA | 15184.82 | 367 | n/a | n/a | Baseline |
| Daily XRP DCA | 42097.10 | 367 | n/a | n/a | Baseline |
| Always-long equal-weight schedule | 9932.39 | 9 | 0.56% | 55.6% | Baseline |
| Random matched schedule | 9789.84 | 9 | 0.13% | 55.6% | Baseline |
| Falling Fed-cut odds -> BTC swing | 10324.44 | 9 | 1.74% | 77.8% | **Rejected** |

## Honest conclusion

> **Rejected.** The signal won on sparse trade-level hit rate, but it still failed the decisive benchmark: it finished far behind **daily BTC DCA** on the same released-capital schedule.

## Decisive checks

- **Doubled-cost check:** final USD fell to **$10,236.09**.
- **Best-trade exclusion:** final USD fell to **$10,106.80**.
- **Interpretation:** the odds filter beat the schedule-matched always-long and random baselines, but that was not enough to overcome the much simpler BTC DCA benchmark in a strong BTC window.

## Files

- `results/fed_hawkish_btc/runs/run-20260808T082630Z/strategy_summary.csv`
- `results/fed_hawkish_btc/runs/run-20260808T082630Z/trade_log.csv`
- `results/fed_hawkish_btc/runs/run-20260808T082630Z/signal_panel.csv`
- `results/fed_hawkish_btc/runs/run-20260808T082630Z/sensitivity_checks.csv`
- `results/fed_hawkish_btc/runs/run-20260808T082630Z/hostile_checks.csv`
