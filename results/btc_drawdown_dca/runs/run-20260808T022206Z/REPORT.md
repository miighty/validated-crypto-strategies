# BTC 72h Drawdown vs DCA Validation

This is historical research on finalized Binance BTC spot candles. It is not a live-trading instruction.

## Data

- Exchange: Binance spot (BTCUSDT)
- Timeframe: 1h OHLCV, signals formed from completed hourly closes and executed no earlier than the next hourly open
- Study sample: 2021-01-01T00:00:00+00:00 to 2026-07-27T23:00:00+00:00
- Coverage rows: 48802
- SHA-256: 8c594e1fb43e69088efd8d5980ae7e6db1e3d7dba7f943bde82ba54f008eeadc

## Primary preregistered rule

- Start with the same fixed $10,000 reserve across all strategies.
- Release that reserve as equal daily contributions at 09:00 UTC across the full sample.
- Daily DCA spends each day’s tranche immediately at that hour’s open.
- Monday weekly DCA spends the accumulated reserve every Monday 09:00 UTC.
- Drawdown strategy buys BTC only when the completed 72-hour close-to-close drawdown is at least 30%, then enters at the next hourly open.
- Drawdown strategy spends the full currently accrued reserve on each qualifying event.
- Cooldown: 24 hours between entries; clustered signals during cooldown are ignored.
- Costs: 0.15% one-way fee+slippage per buy.

## Summary

| Strategy | Final USD value | Final BTC | Costs USD | Event count | Max drawdown | BTC edge vs daily DCA | BTC edge vs weekly DCA |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Daily DCA | 15105.45 | 0.23692641 | 15.00 | 2034 | 54.00% | 0.00000000 | 0.00015251 |
| Monday weekly DCA | 15095.72 | 0.23677389 | 15.00 | 291 | 53.58% | -0.00015251 | 0.00000000 |
| 30% / 72h drawdown buy | 10000.00 | 0.00000000 | 0.00 | 0 | 0.00% | -0.23692641 | -0.23677389 |

## Verdict

**REJECTED** — The primary 30%/72h rule never triggered in the full 2021-2026 BTC sample, while nearby-parameter alternatives still lagged both DCA baselines after costs.

Gate status:

- Primary beats both DCA baselines: `False`
- 2024 validation beats daily DCA: `False`
- 2025+ holdout beats daily DCA: `False`
- Nearby-parameter robustness: `False`
- Hostile checks (exclude best event/year, etc.): `False`
- Doubled-cost robustness: `False`

See `strategy_summary.csv`, `partition_summary.csv`, `drawdown_trade_log.csv`, `sensitivity_checks.csv`, and `hostile_checks.csv` for the full evidence trail.
