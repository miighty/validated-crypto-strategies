# BTC wick flush + supportive odds validation

Run artifact: `results/btc_wick_odds/runs/run-20260808T042807Z/REPORT.md`

## Key findings

- **Primary rule tested:** on `1h` BTC bars, trigger when `low / rolling_max(high.shift(1), 48h) - 1 <= -10%`, require the composite YES odds across **BTC ETF / ETH ETF / Trump / Bitcoin reserve** markets to be down no worse than **2 points over 24h**, then wait for the first close within **24h** that is at least **3% above the event low**; enter at the **next hourly open**, hold **72h**, cooldown **48h**.
- **Benchmarking method:** same fixed **$10,000** reserve released as equal daily contributions, compared against **daily BTC DCA** and **weekly Monday BTC DCA**.
- **Sample window:** `2023-10-01` through `2026-07-27` using real Binance BTC spot hourly bars plus real Polymarket hourly odds.

## Result table

| Strategy | Final USD | Final BTC-equivalent | Events | Avg trade | Win rate | Verdict |
|---|---:|---:|---:|---:|---:|---|
| Daily BTC DCA | 9245.23 | 0.14500987 | 1031 | n/a | n/a | Baseline |
| Weekly BTC DCA | 9212.22 | 0.14449216 | 148 | n/a | n/a | Baseline |
| BTC wick + supportive odds rebound | 10846.03 | 0.17011815 | 6 | 4.81% | 100% | **Promising but inconclusive** |

## Why it stays inconclusive

- The rule **beat both DCA baselines**, including on the untouched `2025+` holdout slice.
- Nearby wick / bounce / hold variants were **mostly still positive**, and the primary rule **survived doubled costs**.
- But the sample is still only **6 total trades**, with just **2 holdout trades**.
- Hostile check: **removing the single best event flips the edge negative vs both DCA baselines**.

## Honest conclusion

> **Promising but inconclusive.** This is the first Polymarket-gated BTC panic-buy rule here with real after-cost outperformance versus both DCA baselines, but the evidence is still too sparse and too concentrated in one event to treat as validated edge.

## Files

- `results/btc_wick_odds/runs/run-20260808T042807Z/REPORT.md`
- `results/btc_wick_odds/runs/run-20260808T042807Z/strategy_summary.csv`
- `results/btc_wick_odds/runs/run-20260808T042807Z/trade_log.csv`
- `results/btc_wick_odds/runs/run-20260808T042807Z/sensitivity_checks.csv`
- `results/btc_wick_odds/runs/run-20260808T042807Z/hostile_checks.csv`
