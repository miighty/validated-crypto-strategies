# BTC ETF Odds -> BTC Swing Validation

Run artifact: `results/btc_etf/runs/run-20260808T030340Z/REPORT.md`

## Key findings

- **Primary rule tested:** BTC ETF YES odds jump by at least **10 points over 24h**, remain at or above **60%**, enter **long BTC** at the **next hourly open**, hold **72h**, then return to cash.
- **Benchmarking method:** same $10,000 reserve released as equal daily contributions across the active market window, compared against **daily BTC DCA** and **weekly Monday BTC DCA**.
- **Sample window:** 2023-10-01 through 2024-01-14 using Binance BTC spot hourly data plus real Polymarket hourly YES odds for `bitcoin-etf-approved-by-jan-15`.

## Scoreboard

| Strategy | Final USD | Final BTC-equivalent | Events | Verdict |
|---|---:|---:|---:|---|
| Daily BTC DCA | 11588.97 | 0.27769755 | 102 | Baseline |
| Weekly BTC DCA | 11478.67 | 0.27505453 | 15 | Baseline |
| BTC ETF odds -> BTC swing | 10173.68 | 0.24378397 | 3 | Rejected |

## Why it failed

- The rule **lost to both BTC DCA baselines** despite the favorable ETF narrative window.
- Hostile check `exclude_best_event` failed badly: removing the best trade leaves the strategy far behind both baselines.
- Nearby threshold / hold variants also failed, so this was **not** a case of the right idea with the wrong exact threshold.

## Best honest conclusion

> **Rejected.** Real BTC ETF approval-odds shocks did not beat simple BTC accumulation in this sample.

## Files

- `results/btc_etf/runs/run-20260808T030340Z/REPORT.md`
- `results/btc_etf/runs/run-20260808T030340Z/strategy_summary.csv`
- `results/btc_etf/runs/run-20260808T030340Z/trade_log.csv`
- `results/btc_etf/runs/run-20260808T030340Z/hostile_checks.csv`
