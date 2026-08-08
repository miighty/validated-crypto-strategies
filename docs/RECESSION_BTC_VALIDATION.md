# Recession odds -> BTC relief validation

Run artifact: `results/recession_btc/runs/run-20260808T074347Z/REPORT.md`

## Key findings

- **Primary rule tested:** when real Polymarket **US recession YES odds** fall by at least **5 points over 24h** and remain at or below **45%**, enter **spot BTC long** at the **next hourly open**, hold **72h**, then exit and wait **24h** before the next entry.
- **Sample:** `2025-09-30` through the pinned repo cutoff using real Polymarket hourly YES odds plus real Binance BTC/ETH/SOL/XRP hourly spot candles.
- **Benchmarks:** same fixed **$10,000** reserve released as equal daily contributions, compared against **daily BTC, ETH, SOL, and XRP DCA** plus **same-schedule always-long equal-weight** and **random-asset schedule** baselines.

## Result table

| Strategy | Final USD | Trades | Avg trade | Win rate | Verdict |
|---|---:|---:|---:|---:|---|
| Daily BTC DCA | 8122.20 | 301 | n/a | n/a | Baseline |
| Daily ETH DCA | 7936.99 | 301 | n/a | n/a | Baseline |
| Daily SOL DCA | 7408.10 | 301 | n/a | n/a | Baseline |
| Daily XRP DCA | 6849.14 | 301 | n/a | n/a | Baseline |
| Always-long equal-weight schedule | 10203.58 | 15 | 0.19% | 53.3% | Baseline |
| Random matched schedule | 10275.76 | 15 | 0.12% | 46.7% | Baseline |
| Recession odds -> BTC relief | 10215.69 | 15 | 0.24% | 53.3% | **Rejected** |

## Honest conclusion

> **Rejected.** The rule beat all four DCA baselines over this bearish sample, but that edge was **not unique to the recession-odds filter**: a same-trade-count random asset schedule finished **higher** at **$10,275.76**.

## Decisive checks

- **Doubled-cost check:** final USD fell to **$10,086.60**.
- **Best-trade exclusion:** final USD stayed near flat at **$10,213.68**.
- **Holdout:** only **3 holdout trades** after `2026-04-01`, so confidence would have remained limited even without the random-baseline failure.

## Files

- `results/recession_btc/runs/run-20260808T074347Z/strategy_summary.csv`
- `results/recession_btc/runs/run-20260808T074347Z/trade_log.csv`
- `results/recession_btc/runs/run-20260808T074347Z/signal_panel.csv`
- `results/recession_btc/runs/run-20260808T074347Z/sensitivity_checks.csv`
- `results/recession_btc/runs/run-20260808T074347Z/hostile_checks.csv`
