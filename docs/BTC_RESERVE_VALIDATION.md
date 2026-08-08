# Bitcoin Reserve Odds -> BTC Swing Validation

Run artifact: `results/btc_reserve/runs/run-20260808T010746Z/REPORT.md`

## Key findings

- **Primary rule tested:** Bitcoin-reserve YES odds rise by at least **5 points over 48h**, remain at or above **35%**, enter **long BTC** at the next hourly open, hold **168h**, then return to cash.
- **Benchmarking method:** same $10,000 reserve released as equal daily contributions through the active market window, compared against **daily BTC DCA** and **weekly Monday BTC DCA**.
- **Sample window:** 2025-03-07 through 2025-05-14 (market life plus hold buffer).

## Result table

| Strategy | Final USD | Final BTC-equivalent | Events | Verdict |
|---|---:|---:|---:|---|
| Daily BTC DCA | 12185.81 | 0.11728778 | 54 | Baseline |
| Weekly BTC DCA | 12243.24 | 0.11784051 | 9 | Baseline |
| Bitcoin reserve odds -> BTC swing | 10004.59 | 0.09629359 | 1 | Inconclusive |

## Honest read

- The single triggered trade was profitable in USD, but **far behind both BTC DCA baselines** in BTC terms.
- Nearby parameter variants and doubled-cost checks **did not rescue the idea**.
- With only **1 trade**, the sample is too small to validate even if the result had beaten DCA.

## Best conclusion

> **Not a validated edge. Current evidence is both tiny-sample and weaker than simple BTC accumulation.**

## Files

- `results/btc_reserve/runs/run-20260808T010746Z/REPORT.md`
- `results/btc_reserve/runs/run-20260808T010746Z/strategy_summary.csv`
- `results/btc_reserve/runs/run-20260808T010746Z/trade_log.csv`
- `results/btc_reserve/runs/run-20260808T010746Z/sensitivity_checks.csv`
- `results/btc_reserve/runs/run-20260808T010746Z/hostile_checks.csv`
