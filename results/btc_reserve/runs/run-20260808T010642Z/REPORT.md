# Bitcoin Reserve Odds → BTC Swing Validation

Historical research only. This is not a live-trading instruction.

## Data

- BTC source: Binance spot (BTCUSDT)
- Polymarket market: will-trump-create-a-national-bitcoin-reserve-in-his-first-100-days — Will Trump create Bitcoin reserve in first 100 days?
- Study sample: 2025-03-07T00:00:00+00:00 to 2026-07-27T23:00:00+00:00
- Coverage rows: 12192
- BTC SHA-256: 8c594e1fb43e69088efd8d5980ae7e6db1e3d7dba7f943bde82ba54f008eeadc

## Primary preregistered rule

- Same $10,000 reserve for all strategies, released as equal daily contributions at 09:00 UTC.
- Daily BTC DCA spends each daily tranche immediately.
- Weekly BTC DCA spends the accumulated reserve every Monday 09:00 UTC.
- Swing strategy waits for Bitcoin-reserve YES odds to rise by at least 5 points over 48 completed hours and remain at or above 35%.
- Entry: next hourly open after the completed signal bar.
- Position: long BTC for 168 hours using the full currently accrued reserve, then return to cash.
- Cooldown: 72 hours after exit.
- Cost model: 0.15% one-way; round-trip BTC cost = 0.30%.

## Summary

| Strategy | Final USD | Final BTC-equivalent | Costs USD | Events | Max DD | BTC edge vs daily | BTC edge vs weekly |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Daily BTC DCA | 7351.20 | 0.11530236 | 15.00 | 508 | 30.33% | 0.00000000 | -0.00020853 |
| Weekly BTC DCA | 7364.50 | 0.11551089 | 15.00 | 73 | 29.94% | 0.00020853 | 0.00000000 |
| Bitcoin reserve odds → BTC swing | 10000.49 | 0.15685598 | 0.18 | 1 | 5.36% | 0.04155361 | 0.04134509 |

## Verdict

- Verdict: **inconclusive**
- Reason: The reserve-odds signal exists, but fewer than 3 trades is not enough to validate against BTC DCA.
- Beats both DCA baselines: **True**
- Nearby-parameter pass rate: **100.00%**
- Doubled-cost pass: **True**
- Hostile checks pass: **True**

## Files

- `strategy_summary.csv`
- `trade_log.csv`
- `equity_curves.csv`
- `partition_summary.csv`
- `sensitivity_checks.csv`
- `hostile_checks.csv`
- `btc_reserve_hourly_odds.csv`
