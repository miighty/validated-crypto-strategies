# Breakout Compression Validation

Run artifact: `results/breakout_compression/runs/run-20260808T003008Z/REPORT.md`

## Key findings

- **Primary test:** accepted 4h breakout longs on BTC/ETH/SOL with a prior-only ATR compression filter; selected threshold = **0.50**.
- **Validation gate vs parent:** selected return **148.59%** vs unfiltered parent **171.35%**.
- **Forward 2024–2026:** selected return **15.00%** vs parent **17.72%**.
- **Same-universe DCA benchmarks:** basket daily DCA **284.77%**, basket weekly DCA **281.97%**.

## Honest conclusion

**REJECTED**. The decisive hostile checks are in `hostile_checks.csv`; no proxy or synthetic inputs were used.

## Files

- `results/breakout_compression/runs/run-20260808T003008Z/REPORT.md`
- `results/breakout_compression/runs/run-20260808T003008Z/strategy_summary.csv`
- `results/breakout_compression/runs/run-20260808T003008Z/partition_summary.csv`
- `results/breakout_compression/runs/run-20260808T003008Z/benchmark_summary.csv`
- `results/breakout_compression/runs/run-20260808T003008Z/hostile_checks.csv`
