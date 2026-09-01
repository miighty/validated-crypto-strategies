# OI-Confirmed Daily Breakout Continuation (Long-Only) Validation

## Primary rule
> LONG-ONLY: enter at next daily open when (a) close breaks above the trailing prior-only 20-day high AND (b) most recent completed daily open interest is >= +5% higher than 5 days earlier. Exit at next daily open on the first close below the trailing prior-only 10-day low. Flat otherwise, non-overlapping trades. 30bps round-trip cost.

## Data sources
- Real Binance spot 1d OHLCV (already cached, `data/raw/*_1d.csv.gz`).
- Real Binance USD-M futures open interest (already cached this program, `data/open_interest/*_oi_daily.csv.gz`, fetched from the public `data.binance.vision` daily-metrics archive). No synthetic/proxy OI used.

## Per-asset results
### BTC
- OI data starts: **2020-09-01** (real archive coverage limit)
- Trades: **31** (mean hold 21.8d)
- Primary final capital: **$409,248.12** (start $10,000)
- Buy-and-hold final: **$54,646.39**
- Daily DCA final: **$16,838.20**
- Unconfirmed-breakout control (no OI filter) final: **$1,635,297.12** (45 trades)
- Seeded random-timing control final: **$16,732.72** (31 trades)
- Doubled-cost final: **$390,612.79**
- Best-trade-exclusion final: **$235,180.85**
- Top single-trade % of total PnL: **3.0956109757682397**
- Gates: {'beats_cash': True, 'beats_bh': True, 'beats_dca': True, 'beats_unconfirmed_breakout_control': False, 'beats_random_control': True, 'survives_doubled_cost': True, 'survives_best_trade_exclusion': True, 'concentration_ok': True, 'has_holdout_trades': True}
- Verdict: **REJECTED**

Partition breakdown:
| asset | partition | n_trades | mean_trade_return_pct |
| --- | --- | --- | --- |
| BTC | development_pre_2024 | 18 | 17.3140 |
| BTC | validation_2024 | 6 | 16.2565 |
| BTC | test_2025_onward | 7 | 6.5044 |

### ETH
- OI data starts: **2021-12-01** (real archive coverage limit)
- Trades: **24** (mean hold 18.9d)
- Primary final capital: **$147,406.03** (start $10,000)
- Buy-and-hold final: **$4,081.20**
- Daily DCA final: **$8,650.03**
- Unconfirmed-breakout control (no OI filter) final: **$381,970.49** (36 trades)
- Seeded random-timing control final: **$9,928.90** (24 trades)
- Doubled-cost final: **$142,182.25**
- Best-trade-exclusion final: **$102,055.48**
- Top single-trade % of total PnL: **4.134040307946255**
- Gates: {'beats_cash': True, 'beats_bh': True, 'beats_dca': True, 'beats_unconfirmed_breakout_control': False, 'beats_random_control': True, 'survives_doubled_cost': True, 'survives_best_trade_exclusion': True, 'concentration_ok': True, 'has_holdout_trades': True}
- Verdict: **REJECTED**

Partition breakdown:
| asset | partition | n_trades | mean_trade_return_pct |
| --- | --- | --- | --- |
| ETH | development_pre_2024 | 10 | 14.2723 |
| ETH | validation_2024 | 6 | 11.4642 |
| ETH | test_2025_onward | 8 | 12.7734 |

### SOL
- OI data starts: **2021-12-01** (real archive coverage limit)
- Trades: **21** (mean hold 19.0d)
- Primary final capital: **$406,028.61** (start $10,000)
- Buy-and-hold final: **$3,553.08**
- Daily DCA final: **$14,487.99**
- Unconfirmed-breakout control (no OI filter) final: **$1,547,775.22** (33 trades)
- Seeded random-timing control final: **$49,393.32** (21 trades)
- Doubled-cost final: **$393,410.10**
- Best-trade-exclusion final: **$92,056.55**
- Top single-trade % of total PnL: **24.336042680525466**
- Gates: {'beats_cash': True, 'beats_bh': True, 'beats_dca': True, 'beats_unconfirmed_breakout_control': False, 'beats_random_control': True, 'survives_doubled_cost': True, 'survives_best_trade_exclusion': True, 'concentration_ok': False, 'has_holdout_trades': True}
- Verdict: **REJECTED**

Partition breakdown:
| asset | partition | n_trades | mean_trade_return_pct |
| --- | --- | --- | --- |
| SOL | development_pre_2024 | 9 | 54.7503 |
| SOL | validation_2024 | 6 | 14.3967 |
| SOL | test_2025_onward | 6 | 8.1437 |

### XRP
- OI data starts: **2021-12-01** (real archive coverage limit)
- Trades: **25** (mean hold 15.6d)
- Primary final capital: **$257,915.78** (start $10,000)
- Buy-and-hold final: **$10,662.09**
- Daily DCA final: **$15,547.78**
- Unconfirmed-breakout control (no OI filter) final: **$944,566.20** (28 trades)
- Seeded random-timing control final: **$7,887.35** (25 trades)
- Doubled-cost final: **$248,402.03**
- Best-trade-exclusion final: **$65,795.13**
- Top single-trade % of total PnL: **48.18207137808205**
- Gates: {'beats_cash': True, 'beats_bh': True, 'beats_dca': True, 'beats_unconfirmed_breakout_control': False, 'beats_random_control': True, 'survives_doubled_cost': True, 'survives_best_trade_exclusion': True, 'concentration_ok': False, 'has_holdout_trades': True}
- Verdict: **REJECTED**

Partition breakdown:
| asset | partition | n_trades | mean_trade_return_pct |
| --- | --- | --- | --- |
| XRP | development_pre_2024 | 11 | 10.3886 |
| XRP | validation_2024 | 5 | 69.3892 |
| XRP | test_2025_onward | 9 | 6.6618 |

## Overall verdict
0/4 assets cleared every gate.

**REJECTED** -- no asset cleared every gate.
