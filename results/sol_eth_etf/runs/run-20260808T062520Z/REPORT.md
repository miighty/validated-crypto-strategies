# SOL ETF Odds → SOL/ETH Spread Validation

Historical research only. This is not a live-trading instruction.

## Data

- SOL source: Binance spot (SOLUSDT)
- ETH source: Binance spot (ETHUSDT)
- Polymarket market: solana-etf-approved-by-july-31-2025 — Solana ETF approved by July 31?
- Study sample: 2024-01-01T00:00:00+00:00 to 2026-07-27T23:00:00+00:00
- Coverage rows: 22536
- SOL SHA-256: 1ca418b22b2ff84376a7d38b7b3e8e0a9578e2351b176ebcc9f6c33058f6a694
- ETH SHA-256: 2de408f963ab72324e508830740f1477818d8c80417b33bbdd4cd4889f221058

## Primary rule frozen for this run

- Same $10,000 reserve for all strategies, released as equal daily contributions at 09:00 UTC.
- Daily SOL DCA spends each daily tranche immediately.
- Weekly SOL DCA spends the accumulated reserve every Monday 09:00 UTC.
- Spread strategy waits for the SOL ETF Polymarket YES probability to jump by at least 10 points over 24 hours and remain at or above 55%.
- Entry: next hourly open after the completed signal bar.
- Position: long SOL / short ETH spread for 72 hours, using the full currently accrued reserve as margin capital.
- Cooldown: 24 hours after exit.
- Cost model: 0.15% one-way per leg; spread round-trip cost = 0.60%.

## Summary

| Strategy | Final USD | Final SOL-equivalent | Costs USD | Events | Max DD | SOL edge vs daily | SOL edge vs weekly |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Daily SOL DCA | 5633.59 | 75.92437724 | 15.00 | 939 | 63.05% | 0.00000000 | -0.18301364 |
| Weekly SOL DCA | 5647.17 | 76.10739088 | 15.00 | 135 | 62.85% | 0.18301364 | 0.00000000 |
| SOL ETF odds → SOL/ETH spread | 10644.46 | 143.45632304 | 284.29 | 9 | 10.15% | 67.53194581 | 67.34893217 |

## Verdict

- Verdict: **rejected**
- Reason: The edge does not survive enough of the DCA, robustness, holdout, or cost checks.
- Beats both DCA baselines: **True**
- Holdout 2025+ pass: **True**
- Nearby-parameter pass rate: **100.00%**
- Doubled-cost pass: **True**
- Hostile checks pass: **False**

## Files

- `strategy_summary.csv`
- `trade_log.csv`
- `equity_curves.csv`
- `partition_summary.csv`
- `sensitivity_checks.csv`
- `hostile_checks.csv`
- `sol_etf_hourly_odds.csv`
