# Crowded Perpetual Unwind (Funding + Open-Interest Joint Extreme, Short-Only) Validation

## Primary rule
> SHORT-ONLY: enter short at next hourly open when (a) trailing mean of last 3 completed 8h funding prints >= +5bps/8h AND (b) most recent completed daily open interest is >= +5% higher than 5 days earlier AND (c) the hourly close breaks below the trailing prior-only 24h low for the first time since the joint condition became true. Hold 48h fixed, then flat, 24h cooldown before re-entry. Funding received each completed 8h print while short. 30bps round-trip cost.

## Data sources
- Real Binance USD-M perpetual funding history (already cached, `data/funding/*.csv.gz`).
- Real Binance spot 1h OHLCV (already cached, `data/raw/*_1h.csv.gz`) as execution/price proxy for the perp.
- Real Binance USD-M futures open interest, newly fetched this run from the public `data.binance.vision` daily-metrics archive (`data/open_interest/*_oi_daily.csv.gz`). No synthetic/proxy OI used; missing archive days are skipped, never fabricated.

## Per-asset results
### BTC
- OI data starts: **2020-09-01** (real archive coverage limit)
- Trades: **10**
- Primary final capital: **$7,529.35** (start $10,000)
- Buy-and-hold final: **$54,646.39**
- Daily DCA final: **$16,839.57**
- Funding-only control (no OI/no downside-break) final: **$15,097.02** (26 trades)
- Seeded random-timing control final: **$9,718.80** (10 trades)
- Doubled-cost final: **$7,417.00**
- Best-trade-exclusion final: **$9,536.53**
- Top single-trade % of total PnL: **77.56878599480609**
- Gates: {'beats_cash': False, 'beats_bh': False, 'beats_dca': False, 'beats_funding_only_control': False, 'beats_random_control': False, 'survives_doubled_cost': False, 'survives_best_trade_exclusion': False, 'concentration_ok': False, 'has_holdout_trades': False}
- Verdict: **REJECTED**

Partition breakdown:
| asset | partition | n_trades | mean_trade_return_pct |
| --- | --- | --- | --- |
| BTC | development_pre_2024 | 9 | -2.0230 |
| BTC | validation_2024 | 1 | -5.5885 |
| BTC | test_2025_onward | 0 |  |

### ETH
- OI data starts: **2021-12-01** (real archive coverage limit)
- Trades: **2**
- Primary final capital: **$10,921.42** (start $10,000)
- Buy-and-hold final: **$4,081.20**
- Daily DCA final: **$8,653.28**
- Funding-only control (no OI/no downside-break) final: **$11,397.58** (6 trades)
- Seeded random-timing control final: **$9,678.98** (2 trades)
- Doubled-cost final: **$10,888.63**
- Best-trade-exclusion final: **$10,157.05**
- Top single-trade % of total PnL: **86.26026338204537**
- Gates: {'beats_cash': True, 'beats_bh': True, 'beats_dca': True, 'beats_funding_only_control': False, 'beats_random_control': True, 'survives_doubled_cost': True, 'survives_best_trade_exclusion': True, 'concentration_ok': False, 'has_holdout_trades': False}
- Verdict: **REJECTED**

Partition breakdown:
| asset | partition | n_trades | mean_trade_return_pct |
| --- | --- | --- | --- |
| ETH | development_pre_2024 | 0 |  |
| ETH | validation_2024 | 2 | 4.7097 |
| ETH | test_2025_onward | 0 |  |

### SOL
- OI data starts: **2021-12-01** (real archive coverage limit)
- Trades: **3**
- Primary final capital: **$9,901.41** (start $10,000)
- Buy-and-hold final: **$3,553.08**
- Daily DCA final: **$14,489.09**
- Funding-only control (no OI/no downside-break) final: **$10,284.07** (6 trades)
- Seeded random-timing control final: **$9,833.15** (3 trades)
- Doubled-cost final: **$9,856.85**
- Best-trade-exclusion final: **$9,337.43**
- Top single-trade % of total PnL: **-614.5694582280126**
- Gates: {'beats_cash': False, 'beats_bh': True, 'beats_dca': False, 'beats_funding_only_control': False, 'beats_random_control': True, 'survives_doubled_cost': False, 'survives_best_trade_exclusion': False, 'concentration_ok': False, 'has_holdout_trades': False}
- Verdict: **REJECTED**

Partition breakdown:
| asset | partition | n_trades | mean_trade_return_pct |
| --- | --- | --- | --- |
| SOL | development_pre_2024 | 0 |  |
| SOL | validation_2024 | 3 | -0.0393 |
| SOL | test_2025_onward | 0 |  |

### XRP
- OI data starts: **2021-12-01** (real archive coverage limit)
- Trades: **2**
- Primary final capital: **$10,606.87** (start $10,000)
- Buy-and-hold final: **$10,662.09**
- Daily DCA final: **$15,580.24**
- Funding-only control (no OI/no downside-break) final: **$9,030.30** (8 trades)
- Seeded random-timing control final: **$9,802.59** (2 trades)
- Doubled-cost final: **$10,575.03**
- Best-trade-exclusion final: **$9,733.20**
- Top single-trade % of total PnL: **148.7717245198961**
- Gates: {'beats_cash': True, 'beats_bh': False, 'beats_dca': False, 'beats_funding_only_control': True, 'beats_random_control': True, 'survives_doubled_cost': True, 'survives_best_trade_exclusion': False, 'concentration_ok': False, 'has_holdout_trades': False}
- Verdict: **REJECTED**

Partition breakdown:
| asset | partition | n_trades | mean_trade_return_pct |
| --- | --- | --- | --- |
| XRP | development_pre_2024 | 0 |  |
| XRP | validation_2024 | 2 | 3.3179 |
| XRP | test_2025_onward | 0 |  |

## Overall verdict
0/4 assets cleared every gate.

**REJECTED** -- no asset cleared every gate.
