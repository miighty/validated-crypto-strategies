# Moderate positive funding persistence validation

Run artifact: `results/funding_moderate_positive_persistence/runs/run-20260904T204855Z/REPORT.md`

## Key findings

- **Primary rule tested:** across real Binance funding for **BTC / ETH / SOL / XRP / BNB / ADA / DOGE / AVAX / LINK**, if one or more completed 8h funding prints land in the preregistered **+1 to +5 bps** bucket, select the **single most positive** asset below +5 bps, enter **spot long at the next hourly open**, hold **8h**, then exit and wait **24h** before the next trade.
- **Why this is genuinely new:** prior studies already covered **negative funding mean reversion** (<= -5 bps) and **extreme positive funding persistence** (>= +5 bps). This run isolates the middle regime where carry might still persist before becoming too crowded.
- **Sample:** real Binance spot hourly OHLCV plus real Binance USD-M funding history, **2021-01-01 through 2026-07-27**, same pinned repo window as the prior funding studies.
- **Benchmarks:** same fixed **$10,000** reserve released as equal daily contributions, compared against **daily BTC, ETH, SOL, and XRP DCA**, **daily equal-weight 9-asset DCA**, an **always-long same-schedule control**, and a **seeded random-asset same-schedule control**.

## Result table

| Strategy | Final USD | Trades | Avg trade | Win rate | Verdict |
|---|---:|---:|---:|---:|---|
| Daily BTC DCA | 15105.45 | 2034 | n/a | n/a | Baseline |
| Daily ETH DCA | 8602.24 | 2034 | n/a | n/a | Baseline |
| Daily SOL DCA | 19664.59 | 2034 | n/a | n/a | Baseline |
| Daily XRP DCA | 15583.79 | 2034 | n/a | n/a | Baseline |
| Daily equal-weight 9-asset DCA | 10757.07 | 2034 | n/a | n/a | Baseline |
| Always-long same schedule | 3097.88 | 1046 | -0.05% | 50.57% | Baseline |
| Random matched-schedule asset baseline | 2906.77 | 1046 | -0.13% | 46.46% | Baseline |
| Moderate positive funding persistence panel | 2728.86 | 1046 | -0.13% | 45.70% | **Rejected** |

## Decisive diagnostics

- **Primary strategy lost 72.7% of capital** and finished behind **every required DCA baseline**.
  - Best required baseline: **SOL DCA $19,664.59**.
- **The bucket itself is too small after costs at the primary 8h horizon.**
  - Pooled **+1 to +5 bps** events: **12,558** samples.
  - Mean forward return: **+0.126% gross**, but **-0.174% net** after the repo's 30 bps round-trip cost.
  - Zero-funding bucket over the same 8h horizon: **+0.025% gross**.
- **The 2025+ holdout is worse, not better.**
  - Primary strategy holdout sleeve: **$2,728.86** final after **252** trades in the 2025+ partition.
  - Pooled **+1 to +5 bps** holdout events: **1,698** samples with **-0.058% gross** mean forward 8h return before costs.
- **Hostile checks do not rescue it.**
  - Doubled costs: **$1,671.63**.
  - Excluding the best trade: **$2,723.22**.
  - Random matched-schedule control still finished higher: **$2,906.77**.

## Honest conclusion

> **Rejected.** Moderate positive funding on this real Binance universe does not provide enough persistence to clear costs. The economic pattern exists only weakly in gross returns and disappears once realistic round-trip costs are deducted; in the 2025+ holdout it is already negative even before costs.

## Files

- `results/funding_moderate_positive_persistence/runs/run-20260904T204855Z/strategy_summary.csv`
- `results/funding_moderate_positive_persistence/runs/run-20260904T204855Z/trade_log.csv`
- `results/funding_moderate_positive_persistence/runs/run-20260904T204855Z/equity_curves.csv`
- `results/funding_moderate_positive_persistence/runs/run-20260904T204855Z/partition_summary.csv`
- `results/funding_moderate_positive_persistence/runs/run-20260904T204855Z/signal_panel.csv`
- `results/funding_moderate_positive_persistence/runs/run-20260904T204855Z/sensitivity_checks.csv`
- `results/funding_moderate_positive_persistence/runs/run-20260904T204855Z/hostile_checks.csv`
- `results/funding_moderate_positive_persistence/runs/run-20260904T204855Z/bucket_forward_returns.csv`
