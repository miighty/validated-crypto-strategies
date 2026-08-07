# SOL ETF Odds -> SOL/ETH Spread Validation

Run artifact: `results/sol_eth_etf/runs/run-20260807T234807Z/REPORT.md`

## Key findings

- **Primary rule tested:** SOL ETF YES odds jump by at least **10 points over 24h**, remain at or above **55%**, enter **long SOL / short ETH** at the next hourly open, hold **72h**, then exit.
- **Benchmarking method:** same $10,000 reserve released as equal daily contributions across the sample, compared against **daily SOL DCA** and **weekly Monday SOL DCA**.
- **Sample window:** 2024-01-01 through 2026-07-27 using Binance spot SOL/ETH hourly data plus real Polymarket hourly YES odds for `solana-etf-approved-by-july-31-2025`.

## Result table

| Strategy | Final USD | Final SOL-equivalent | Events | Verdict |
|---|---:|---:|---:|---|
| Daily SOL DCA | 5633.59 | 75.92437724 | 939 | Baseline |
| Weekly SOL DCA | 5647.17 | 76.10739088 | 135 | Baseline |
| SOL ETF odds -> SOL/ETH spread | 10644.46 | 143.45632304 | 9 | Rejected |

## Why it was rejected

- The primary spread rule **did beat both SOL DCA baselines** and the nearby-parameter / doubled-cost checks.
- But the edge was **too concentrated in one June 2025 event**.
- Hostile check: removing the single best trade flips the strategy from far ahead of DCA to **behind both DCA baselines**.
- That means the apparent edge is not yet robust enough to carry forward as validated structure.

## Practical interpretation

- This is a **real signal family worth keeping on the board**, because unlike the ETH ETF case it generated a non-trivial sample (`9` trades) and the sign was broadly consistent.
- But current evidence still says **do not upgrade it beyond research status**.
- Best next step is not tighter thresholds; it is **more analogue events** so the same mechanism can be tested on a broader regulatory/ETF set.

## Files

- `results/sol_eth_etf/runs/run-20260807T234807Z/REPORT.md`
- `results/sol_eth_etf/runs/run-20260807T234807Z/strategy_summary.csv`
- `results/sol_eth_etf/runs/run-20260807T234807Z/trade_log.csv`
- `results/sol_eth_etf/runs/run-20260807T234807Z/hostile_checks.csv`
