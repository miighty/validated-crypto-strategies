# XRP ETF Odds -> XRP/BTC Spread Validation

Run artifact: `results/xrp_btc_etf/runs/run-20260808T034547Z/REPORT.md`

## Key findings

- **Primary rule tested:** XRP ETF YES odds jump by at least **10 points over 24h**, remain at or above **55%**, enter **long XRP / short BTC** at the next hourly open, hold **72h**, then exit.
- **Benchmarking method:** same $10,000 reserve released as equal daily contributions across the sample, compared against **daily XRP DCA** and **weekly Monday XRP DCA**.
- **Sample window:** 2025-01-01 through 2026-07-27 using Binance XRP/BTC spot hourly data plus real Polymarket hourly YES odds for `ripple-etf-approved-by-july-31-2025`.

## Result table

| Strategy | Final USD | Final XRP-equivalent | Events | Avg trade | Win rate | Verdict |
|---|---:|---:|---:|---:|---:|---|
| Daily XRP DCA | 5617.32 | 5269.03992057 | 573 | n/a | n/a | Baseline |
| Weekly XRP DCA | 5652.13 | 5301.68429484 | 82 | n/a | n/a | Baseline |
| XRP ETF odds -> XRP/BTC spread | 9854.78 | 9243.76470889 | 4 | -2.54% | 0% | Rejected |

## Why it was rejected

- The strategy **beat both XRP DCA baselines only because it left most capital in cash** during a weak XRP period.
- The actual spread signal itself was bad: **all 4 realized XRP/BTC spread trades lost money after costs**.
- Nearby threshold / hold variants also stayed negative on realized trade returns, so this was **not** a case of the right idea with the wrong exact cutoff.

## Honest conclusion

> **Rejected. This is cash-timing outperformance, not evidence of a profitable XRP/BTC event signal.**

## Files

- `results/xrp_btc_etf/runs/run-20260808T034547Z/REPORT.md`
- `results/xrp_btc_etf/runs/run-20260808T034547Z/strategy_summary.csv`
- `results/xrp_btc_etf/runs/run-20260808T034547Z/trade_log.csv`
- `results/xrp_btc_etf/runs/run-20260808T034547Z/sensitivity_checks.csv`
- `results/xrp_btc_etf/runs/run-20260808T034547Z/hostile_checks.csv`
