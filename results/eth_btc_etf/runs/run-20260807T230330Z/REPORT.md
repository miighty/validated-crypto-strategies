# ETH ETF Odds → ETH/BTC Spread Validation

Historical research only. This is not a live-trading instruction.

## Data

- ETH source: Binance spot (ETHUSDT)
- BTC source: Binance spot (BTCUSDT)
- Polymarket market: ethereum-etf-approved-by-may-31 — Ethereum ETF approved by May 31?
- Study sample: 2021-01-01T00:00:00+00:00 to 2026-07-27T23:00:00+00:00
- Coverage rows: 48802
- ETH SHA-256: 2de408f963ab72324e508830740f1477818d8c80417b33bbdd4cd4889f221058
- BTC SHA-256: 8c594e1fb43e69088efd8d5980ae7e6db1e3d7dba7f943bde82ba54f008eeadc

## Primary preregistered rule

- Same $10,000 reserve for all strategies, released as equal daily contributions at 09:00 UTC.
- Daily ETH DCA spends each daily tranche immediately.
- Weekly ETH DCA spends the accumulated reserve every Monday 09:00 UTC.
- Spread strategy waits for the ETH ETF Polymarket YES probability to jump by at least 10 points over 24 hours and remain at or above 60%.
- Entry: next hourly open after the completed signal bar.
- Position: long ETH / short BTC spread for 72 hours, using the full currently accrued reserve as margin capital.
- Cooldown: 24 hours after exit.
- Cost model: 0.15% one-way per leg; spread round-trip cost = 0.60%.

## Summary

| Strategy | Final USD | Final ETH-equivalent | Costs USD | Events | Max DD | ETH edge vs daily | ETH edge vs weekly |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Daily ETH DCA | 8602.24 | 4.54536410 | 15.00 | 2034 | 71.38% | 0.00000000 | 0.00347274 |
| Weekly ETH DCA | 8595.67 | 4.54189136 | 15.00 | 291 | 70.68% | -0.00347274 | 0.00000000 |
| ETH ETF odds → ETH/BTC spread | 10556.28 | 5.57786601 | 36.46 | 1 | 3.06% | 1.03250191 | 1.03597464 |

## Verdict

- Verdict: **inconclusive**
- Reason: Positive signal exists, but fewer than 3 trades is not enough to validate against DCA.
- Beats both DCA baselines: **True**
- Validation 2024 pass: **False**
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
- `eth_etf_hourly_odds.csv`
