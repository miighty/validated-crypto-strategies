# SOL ETF Odds -> SOL/ETH Spread Validation

Run artifact: `results/sol_eth_etf/runs/run-20260808T062520Z/REPORT.md`

## Key findings

- **Primary rule tested:** when real Polymarket **SOL ETF approval YES odds** jump by at least **10 points over 24h** and remain at or above **55%**, enter **long SOL / short ETH** at the next hourly open, hold **72h**, then exit.
- **Benchmarking method:** same fixed **$10,000** reserve released as equal daily contributions from **2024-01-01** onward, compared against **daily SOL DCA** and **weekly Monday SOL DCA**.
- **Sample window:** 2024-01-01 through 2026-07-27 using real Binance **SOLUSDT / ETHUSDT** hourly spot data plus real Polymarket hourly YES odds for `solana-etf-approved-by-july-31-2025`.

## Result table

| Strategy | Final USD | Final SOL equiv | Trades | Max DD | Verdict |
|---|---:|---:|---:|---:|---|
| Daily SOL DCA | 5633.59 | 75.92437724 | 939 | 63.05% | Baseline |
| Weekly SOL DCA | 5647.17 | 76.10739088 | 135 | 62.85% | Baseline |
| SOL ETF odds -> SOL/ETH spread | 10644.46 | 143.45632304 | 9 | 10.15% | Rejected |

## Why it was rejected

- **Headline return was strong, but the sample stayed tiny:** only **9 trades** total, with **6 holdout trades**.
- **Best-trade dependence was too high:** removing the best event flipped the edge versus daily SOL DCA from **+67.53 SOL** to **-27.90 SOL**.
- **Interpretation:** this is a better analogue than the pooled alt/BTC family, but it still does **not** clear the repo's robustness bar for a validated edge.

## Decisive checks

- **Holdout 2025+ result:** passed on headline return.
- **Doubled-cost check:** still positive at **$10356.83**.
- **Nearby-parameter sweep:** all tested nearby variants still beat the SOL DCA baselines, but the evidence remains too concentrated in very few events.

## Files

- `results/sol_eth_etf/runs/run-20260808T062520Z/strategy_summary.csv`
- `results/sol_eth_etf/runs/run-20260808T062520Z/trade_log.csv`
- `results/sol_eth_etf/runs/run-20260808T062520Z/partition_summary.csv`
- `results/sol_eth_etf/runs/run-20260808T062520Z/sensitivity_checks.csv`
- `results/sol_eth_etf/runs/run-20260808T062520Z/hostile_checks.csv`
