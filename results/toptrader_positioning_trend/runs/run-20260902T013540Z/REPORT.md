# Top-Trader Positioning Trend (SMA10/SMA30) Regime Filter Validation

## Primary rule
> LONG-ONLY per-asset: long while rolling 10-day mean of Binance top-trader long/short position ratio > rolling 30-day mean (smart-money positioning trending up); flat otherwise. Enter/exit one bar after the regime flag changes (no lookahead). 30bps round-trip cost.

## Data sources
- Real Binance USD-M futures daily top-trader long/short position ratio (`data/open_interest/*_oi_daily.csv.gz`, `sum_toptrader_long_short_ratio` column, already cached; coverage BTC from 2020-09-01, ETH/SOL/XRP from 2021-12-01). Never used as a signal in any prior study in this repo.
- Real Binance spot daily OHLCV (`data/raw/*_1d.csv.gz`).

### BTC
- Coverage start used: 2020-09-01
- Regime blocks: **41** (on-fraction 46.4%)
- Primary final (start=1.0): **1.1205**
- Buy-and-hold final: **5.6056**
- Daily DCA final: **1.7272**
- Momentum-regime control final: **11.3431**
- Random-regime control final: **2.7033**
- Doubled-cost final: **0.9906**
- Best-block-excluded final: **2.6104**
- Top block % of PnL: -821.4552856255528
- Gates: {'beats_buy_and_hold': False, 'beats_dca': False, 'beats_momentum_control': False, 'beats_random_control': False, 'survives_doubled_cost': False, 'survives_best_block_exclusion': False, 'concentration_ok': False, 'has_holdout_blocks': True}
- Verdict: **REJECTED**

Partition breakdown:
  - {'asset': 'BTC', 'partition': 'development', 'n_blocks': 19, 'mean_block_return_pct': 2.85346668016531}
  - {'asset': 'BTC', 'partition': 'validation_2024', 'n_blocks': 9, 'mean_block_return_pct': 4.24496275513545}
  - {'asset': 'BTC', 'partition': 'test_2025_onward', 'n_blocks': 13, 'mean_block_return_pct': -0.8448310797692593}

### ETH
- Coverage start used: 2021-12-01
- Regime blocks: **30** (on-fraction 52.9%)
- Primary final (start=1.0): **0.8186**
- Buy-and-hold final: **0.4215**
- Daily DCA final: **0.8934**
- Momentum-regime control final: **2.5996**
- Random-regime control final: **1.7110**
- Doubled-cost final: **0.7480**
- Best-block-excluded final: **1.2201**
- Top block % of PnL: 188.33899151106783
- Gates: {'beats_buy_and_hold': True, 'beats_dca': False, 'beats_momentum_control': False, 'beats_random_control': False, 'survives_doubled_cost': False, 'survives_best_block_exclusion': True, 'concentration_ok': False, 'has_holdout_blocks': True}
- Verdict: **REJECTED**

Partition breakdown:
  - {'asset': 'ETH', 'partition': 'development', 'n_blocks': 9, 'mean_block_return_pct': 0.5820047456705736}
  - {'asset': 'ETH', 'partition': 'validation_2024', 'n_blocks': 9, 'mean_block_return_pct': 3.216995742086959}
  - {'asset': 'ETH', 'partition': 'test_2025_onward', 'n_blocks': 12, 'mean_block_return_pct': -1.4790400752705748}

### SOL
- Coverage start used: 2021-12-01
- Regime blocks: **36** (on-fraction 49.2%)
- Primary final (start=1.0): **0.5507**
- Buy-and-hold final: **0.3676**
- Daily DCA final: **1.4990**
- Momentum-regime control final: **1.2738**
- Random-regime control final: **0.3353**
- Doubled-cost final: **0.4942**
- Best-block-excluded final: **0.1619**
- Top block % of PnL: -180.69464834602687
- Gates: {'beats_buy_and_hold': True, 'beats_dca': False, 'beats_momentum_control': False, 'beats_random_control': True, 'survives_doubled_cost': False, 'survives_best_block_exclusion': False, 'concentration_ok': False, 'has_holdout_blocks': True}
- Verdict: **REJECTED**

Partition breakdown:
  - {'asset': 'SOL', 'partition': 'development', 'n_blocks': 8, 'mean_block_return_pct': 26.635442778179687}
  - {'asset': 'SOL', 'partition': 'validation_2024', 'n_blocks': 11, 'mean_block_return_pct': 4.780117715658496}
  - {'asset': 'SOL', 'partition': 'test_2025_onward', 'n_blocks': 17, 'mean_block_return_pct': -4.964214557506442}

### XRP
- Coverage start used: 2021-12-01
- Regime blocks: **34** (on-fraction 57.6%)
- Primary final (start=1.0): **3.6784**
- Buy-and-hold final: **1.1132**
- Daily DCA final: **1.6233**
- Momentum-regime control final: **1.9711**
- Random-regime control final: **0.9822**
- Doubled-cost final: **3.3212**
- Best-block-excluded final: **0.8091**
- Top block % of PnL: 121.36843460893097
- Gates: {'beats_buy_and_hold': True, 'beats_dca': True, 'beats_momentum_control': True, 'beats_random_control': True, 'survives_doubled_cost': True, 'survives_best_block_exclusion': False, 'concentration_ok': False, 'has_holdout_blocks': True}
- Verdict: **REJECTED**

Partition breakdown:
  - {'asset': 'XRP', 'partition': 'development', 'n_blocks': 13, 'mean_block_return_pct': 0.702604522949762}
  - {'asset': 'XRP', 'partition': 'validation_2024', 'n_blocks': 6, 'mean_block_return_pct': 61.78860149157016}
  - {'asset': 'XRP', 'partition': 'test_2025_onward', 'n_blocks': 15, 'mean_block_return_pct': -0.2766574364733458}

## Overall verdict: **REJECTED** (0/4 assets CANDIDATE)