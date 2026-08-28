# XRP ETF Odds → XRP/BTC Spread Validation

Historical research only. This is not a live-trading instruction.

## Data

- XRP source: Binance spot (XRPUSDT)
- BTC source: Binance spot (BTCUSDT)
- Polymarket market: ripple-etf-approved-by-july-31-2025 — Ripple ETF approved by July 31?
- Study sample: 2025-01-01T00:00:00+00:00 to 2026-07-27T23:00:00+00:00
- Coverage rows: 13752
- XRP SHA-256: 07f195a69b57bd66398d8c51c984bc72253778985d30c1a52d63d0011ccfa0a9
- BTC SHA-256: 8c594e1fb43e69088efd8d5980ae7e6db1e3d7dba7f943bde82ba54f008eeadc

## Primary rule frozen for this run

- Same $10,000 reserve for all strategies, released as equal daily contributions at 09:00 UTC.
- Daily XRP DCA spends each daily tranche immediately.
- Weekly XRP DCA spends the accumulated reserve every Monday 09:00 UTC.
- Spread strategy waits for the XRP ETF Polymarket YES probability to jump by at least 10 points over 24 completed hours and remain at or above 55%.
- Entry: next hourly open after the completed signal bar.
- Position: long XRP / short BTC spread for 72 hours, using the full currently accrued reserve as margin capital.
- Cooldown: 24 hours after exit.
- Cost model: 0.15% one-way per leg; spread round-trip cost = 0.60%.

## Summary

| Strategy | Final USD | Final XRP-equivalent | Costs USD | Events | Max DD | XRP edge vs daily | XRP edge vs weekly |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Daily XRP DCA | 5617.32 | 5269.03992057 | 15.00 | 573 | 46.26% | 0.00000000 | -32.64437427 |
| Weekly XRP DCA | 5652.13 | 5301.68429484 | 15.00 | 82 | 45.81% | 32.64437427 | 0.00000000 |
| XRP ETF odds → XRP/BTC spread | 9854.78 | 9243.76470889 | 34.97 | 4 | 4.97% | 3974.72478833 | 3942.08041406 |

## Verdict

- Verdict: **paper-trading candidate**
- Reason: Primary spread rule beat both DCA baselines and cleared the main robustness gates.
- Beats both DCA baselines: **True**
- Holdout Q2 2025+ pass: **True**
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
- `xrp_etf_hourly_odds.csv`
