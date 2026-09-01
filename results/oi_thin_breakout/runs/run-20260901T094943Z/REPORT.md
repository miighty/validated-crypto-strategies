# OI-Thin (Falling) Daily Breakout Continuation (Long-Only) Validation

## Primary rule
> LONG-ONLY: enter at next daily open when (a) close breaks above the trailing prior-only 20-day high AND (b) most recent completed daily open interest is <= -5% lower than 5 days earlier (mirror image of the rejected OI-rising study's +5% trigger). Exit at next daily open on the first close below the trailing prior-only 10-day low. Flat otherwise, non-overlapping trades. 30bps round-trip cost.

## Data sources
- Real Binance spot 1d OHLCV (already cached, `data/raw/*_1d.csv.gz`).
- Real Binance USD-M futures open interest (already cached this program, `data/open_interest/*_oi_daily.csv.gz`, fetched from the public `data.binance.vision` daily-metrics archive). No synthetic/proxy OI used.

## Genealogy
This is the explicit recommended follow-up from EXP-2026-09-01-OIBREAKOUT-001 (rejected: OI-RISING confirmation lost 2.7x-4.0x to the unconfirmed breakout control on all 4 assets). Same breakout/exit structure, same magnitude threshold (5%), opposite sign (OI falling = thin positioning, room to add) -- not a re-tune.

## Per-asset results
### BTC
- OI data starts: **2020-09-01** (real archive coverage limit)
- Trades: **21** (mean hold 21.8d)
- Primary (OI-thin) final capital: **$139,264.24** (start $10,000)
- Buy-and-hold final: **$54,646.39**
- Daily DCA final: **$16,838.20**
- Unconfirmed-breakout control (no OI filter) final: **$1,635,297.12** (45 trades)
- OI-RISING variant (rejected study, direct comparison) final: **$409,248.12** (31 trades)
- Seeded random-timing control final: **$7,348.50** (21 trades)
- Doubled-cost final: **$134,936.20**
- Best-trade-exclusion final: **$92,517.34**
- Top single-trade % of total PnL: **4.857723848895798**
- Gates: {'beats_cash': True, 'beats_bh': True, 'beats_dca': True, 'beats_unconfirmed_breakout_control': False, 'beats_oi_rising_variant': False, 'beats_random_control': True, 'survives_doubled_cost': True, 'survives_best_trade_exclusion': True, 'concentration_ok': True, 'has_holdout_trades': True}
- Verdict: **REJECTED**

Partition breakdown:
| asset | partition | n_trades | mean_trade_return_pct |
| --- | --- | --- | --- |
| BTC | development_pre_2024 | 12 | 16.3534 |
| BTC | validation_2024 | 5 | 18.8637 |
| BTC | test_2025_onward | 4 | 5.1202 |

### ETH
- OI data starts: **2021-12-01** (real archive coverage limit)
- Trades: **16** (mean hold 15.1d)
- Primary (OI-thin) final capital: **$27,464.74** (start $10,000)
- Buy-and-hold final: **$4,081.20**
- Daily DCA final: **$8,650.03**
- Unconfirmed-breakout control (no OI filter) final: **$381,970.49** (36 trades)
- OI-RISING variant (rejected study, direct comparison) final: **$147,406.03** (24 trades)
- Seeded random-timing control final: **$19,099.42** (16 trades)
- Doubled-cost final: **$26,811.98**
- Best-trade-exclusion final: **$18,876.65**
- Top single-trade % of total PnL: **43.52627263243904**
- Gates: {'beats_cash': True, 'beats_bh': True, 'beats_dca': True, 'beats_unconfirmed_breakout_control': False, 'beats_oi_rising_variant': False, 'beats_random_control': True, 'survives_doubled_cost': True, 'survives_best_trade_exclusion': True, 'concentration_ok': False, 'has_holdout_trades': True}
- Verdict: **REJECTED**

Partition breakdown:
| asset | partition | n_trades | mean_trade_return_pct |
| --- | --- | --- | --- |
| ETH | development_pre_2024 | 12 | 4.1281 |
| ETH | validation_2024 | 2 | 23.8721 |
| ETH | test_2025_onward | 2 | 10.8027 |

### SOL
- OI data starts: **2021-12-01** (real archive coverage limit)
- Trades: **13** (mean hold 18.5d)
- Primary (OI-thin) final capital: **$171,502.52** (start $10,000)
- Buy-and-hold final: **$3,553.08**
- Daily DCA final: **$14,487.99**
- Unconfirmed-breakout control (no OI filter) final: **$1,547,775.22** (33 trades)
- OI-RISING variant (rejected study, direct comparison) final: **$406,028.61** (21 trades)
- Seeded random-timing control final: **$11,477.48** (13 trades)
- Doubled-cost final: **$168,183.22**
- Best-trade-exclusion final: **$49,530.30**
- Top single-trade % of total PnL: **39.42637288657816**
- Gates: {'beats_cash': True, 'beats_bh': True, 'beats_dca': True, 'beats_unconfirmed_breakout_control': False, 'beats_oi_rising_variant': False, 'beats_random_control': True, 'survives_doubled_cost': True, 'survives_best_trade_exclusion': True, 'concentration_ok': False, 'has_holdout_trades': True}
- Verdict: **REJECTED**

Partition breakdown:
| asset | partition | n_trades | mean_trade_return_pct |
| --- | --- | --- | --- |
| SOL | development_pre_2024 | 9 | 40.8415 |
| SOL | validation_2024 | 3 | 26.7602 |
| SOL | test_2025_onward | 1 | -0.4871 |

### XRP
- OI data starts: **2021-12-01** (real archive coverage limit)
- Trades: **8** (mean hold 15.5d)
- Primary (OI-thin) final capital: **$39,392.82** (start $10,000)
- Buy-and-hold final: **$10,662.09**
- Daily DCA final: **$15,547.78**
- Unconfirmed-breakout control (no OI filter) final: **$944,566.20** (28 trades)
- OI-RISING variant (rejected study, direct comparison) final: **$257,915.78** (25 trades)
- Seeded random-timing control final: **$11,677.69** (8 trades)
- Doubled-cost final: **$38,921.88**
- Best-trade-exclusion final: **$19,343.31**
- Top single-trade % of total PnL: **65.20390208479506**
- Gates: {'beats_cash': True, 'beats_bh': True, 'beats_dca': True, 'beats_unconfirmed_breakout_control': False, 'beats_oi_rising_variant': False, 'beats_random_control': True, 'survives_doubled_cost': True, 'survives_best_trade_exclusion': True, 'concentration_ok': False, 'has_holdout_trades': True}
- Verdict: **REJECTED**

Partition breakdown:
| asset | partition | n_trades | mean_trade_return_pct |
| --- | --- | --- | --- |
| XRP | development_pre_2024 | 6 | 11.2031 |
| XRP | validation_2024 | 1 | 106.1113 |
| XRP | test_2025_onward | 1 | 5.9776 |

## Overall verdict
0/4 assets cleared every gate.

**REJECTED** -- no asset cleared every gate.
