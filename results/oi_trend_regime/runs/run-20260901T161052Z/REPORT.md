# Open-Interest Trend (SMA20/SMA60 Crossover) Regime Filter Validation

## Primary rule
> LONG-ONLY per-asset: long while rolling 20-day mean of daily open interest > rolling 60-day mean; flat otherwise. Enter/exit one bar after the regime flag changes (no lookahead). 30bps round-trip cost.

## Data sources
- Real Binance USD-M futures daily OI (`data/open_interest/*_oi_daily.csv.gz`, already cached, coverage BTC from 2020-09-01, ETH/SOL/XRP from 2021-12-01).
- Real Binance spot daily OHLCV (`data/raw/*_1d.csv.gz`).

### BTC
- OI coverage start used: 2020-09-01
- Regime blocks: **30** (on-fraction 56.3%)
- Primary final (start=1.0): **0.5063**
- Buy-and-hold final: **5.6056**
- Daily DCA final: **1.7272**
- Momentum-regime control final: **11.3431**
- Random-regime control final: **1.4837**
- Doubled-cost final: **0.4626**
- Best-block-excluded final: **0.3036**
- Top block % of PnL: 70.98972770295596
- Gates: {'beats_buy_and_hold': False, 'beats_dca': False, 'beats_momentum_control': False, 'beats_random_control': False, 'survives_doubled_cost': False, 'survives_best_block_exclusion': False, 'concentration_ok': False, 'has_holdout_blocks': True}
- Verdict: **REJECTED**

Partition breakdown:
  - {'asset': 'BTC', 'partition': 'development', 'n_blocks': 18, 'mean_block_return_pct': -2.7624766165467234}
  - {'asset': 'BTC', 'partition': 'validation_2024', 'n_blocks': 6, 'mean_block_return_pct': 10.80888924707845}
  - {'asset': 'BTC', 'partition': 'test_2025_onward', 'n_blocks': 6, 'mean_block_return_pct': -2.364366597691077}

### ETH
- OI coverage start used: 2021-12-01
- Regime blocks: **18** (on-fraction 57.8%)
- Primary final (start=1.0): **1.2832**
- Buy-and-hold final: **0.4215**
- Daily DCA final: **0.8934**
- Momentum-regime control final: **2.5996**
- Random-regime control final: **0.3006**
- Doubled-cost final: **1.2156**
- Best-block-excluded final: **0.5875**
- Top block % of PnL: 380.1202632433275
- Gates: {'beats_buy_and_hold': True, 'beats_dca': True, 'beats_momentum_control': False, 'beats_random_control': True, 'survives_doubled_cost': True, 'survives_best_block_exclusion': True, 'concentration_ok': False, 'has_holdout_blocks': True}
- Verdict: **REJECTED**

Partition breakdown:
  - {'asset': 'ETH', 'partition': 'development', 'n_blocks': 10, 'mean_block_return_pct': -3.7323318691353657}
  - {'asset': 'ETH', 'partition': 'validation_2024', 'n_blocks': 4, 'mean_block_return_pct': 14.807178780925797}
  - {'asset': 'ETH', 'partition': 'test_2025_onward', 'n_blocks': 4, 'mean_block_return_pct': 20.22096450481427}

### SOL
- OI coverage start used: 2021-12-01
- Regime blocks: **21** (on-fraction 57.7%)
- Primary final (start=1.0): **1.5788**
- Buy-and-hold final: **0.3676**
- Daily DCA final: **1.4990**
- Momentum-regime control final: **1.2738**
- Random-regime control final: **0.1035**
- Doubled-cost final: **1.4822**
- Best-block-excluded final: **0.7442**
- Top block % of PnL: 144.60797789809976
- Gates: {'beats_buy_and_hold': True, 'beats_dca': True, 'beats_momentum_control': True, 'beats_random_control': True, 'survives_doubled_cost': True, 'survives_best_block_exclusion': True, 'concentration_ok': False, 'has_holdout_blocks': True}
- Verdict: **REJECTED**

Partition breakdown:
  - {'asset': 'SOL', 'partition': 'development', 'n_blocks': 10, 'mean_block_return_pct': 11.484214578256422}
  - {'asset': 'SOL', 'partition': 'validation_2024', 'n_blocks': 5, 'mean_block_return_pct': 11.210046656988764}
  - {'asset': 'SOL', 'partition': 'test_2025_onward', 'n_blocks': 6, 'mean_block_return_pct': 5.228578916411423}

### XRP
- OI coverage start used: 2021-12-01
- Regime blocks: **21** (on-fraction 59.1%)
- Primary final (start=1.0): **1.6549**
- Buy-and-hold final: **1.1132**
- Daily DCA final: **1.6233**
- Momentum-regime control final: **1.9711**
- Random-regime control final: **0.5038**
- Doubled-cost final: **1.5537**
- Best-block-excluded final: **0.4580**
- Top block % of PnL: 272.58382331232366
- Gates: {'beats_buy_and_hold': True, 'beats_dca': True, 'beats_momentum_control': False, 'beats_random_control': True, 'survives_doubled_cost': True, 'survives_best_block_exclusion': False, 'concentration_ok': False, 'has_holdout_blocks': True}
- Verdict: **REJECTED**

Partition breakdown:
  - {'asset': 'XRP', 'partition': 'development', 'n_blocks': 9, 'mean_block_return_pct': -0.6169298249684572}
  - {'asset': 'XRP', 'partition': 'validation_2024', 'n_blocks': 4, 'mean_block_return_pct': 61.94759901214677}
  - {'asset': 'XRP', 'partition': 'test_2025_onward', 'n_blocks': 8, 'mean_block_return_pct': -3.1581693794844714}

## Overall verdict
0/4 assets cleared every gate.

**REJECTED** -- no asset cleared every gate.