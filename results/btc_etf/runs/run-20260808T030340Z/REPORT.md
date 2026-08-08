# BTC ETF Odds → BTC Swing Validation

Historical research only. This is not a live-trading instruction.

## Data

- BTC source: Binance spot (BTCUSDT)
- Polymarket market: bitcoin-etf-approved-by-jan-15 — Bitcoin ETF approved by Jan 15?
- Study sample: 2023-10-01T00:00:00+00:00 to 2024-01-14T23:00:00+00:00
- Coverage rows: 2544
- BTC SHA-256: 8c594e1fb43e69088efd8d5980ae7e6db1e3d7dba7f943bde82ba54f008eeadc

## Primary preregistered rule

- Same $10,000 reserve for all strategies, released as equal daily contributions at 09:00 UTC across the active market window.
- Daily BTC DCA spends each daily tranche immediately.
- Weekly BTC DCA spends the accumulated reserve every Monday 09:00 UTC.
- Swing strategy waits for BTC ETF YES odds to rise by at least 10 points over 24 completed hours and remain at or above 60%.
- Entry: next hourly open after the completed signal bar.
- Position: long BTC for 72 hours using the full currently accrued reserve, then return to cash.
- Cooldown: 24 hours after exit.
- Cost model: 0.15% one-way; round-trip BTC cost = 0.30%.

## Summary

| Strategy | Final USD | Final BTC-equivalent | Costs USD | Events | Max DD | BTC edge vs daily | BTC edge vs weekly |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Daily BTC DCA | 11588.97 | 0.27769755 | 15.00 | 102 | 14.08% | 0.00000000 | 0.00264302 |
| Weekly BTC DCA | 11478.67 | 0.27505453 | 14.71 | 15 | 13.87% | -0.00264302 | 0.00000000 |
| BTC ETF odds → BTC swing | 10173.68 | 0.24378397 | 78.35 | 3 | 6.95% | -0.03391358 | -0.03127056 |

## Verdict

- Verdict: **rejected**
- Reason: The edge does not survive enough of the DCA, robustness, concentration, or cost checks.
- Beats both DCA baselines: **False**
- Nearby-parameter pass rate: **0.00%**
- Doubled-cost pass: **False**
- Hostile checks pass: **False**

## Files

- `strategy_summary.csv`
- `trade_log.csv`
- `equity_curves.csv`
- `partition_summary.csv`
- `sensitivity_checks.csv`
- `hostile_checks.csv`
- `btc_etf_hourly_odds.csv`
