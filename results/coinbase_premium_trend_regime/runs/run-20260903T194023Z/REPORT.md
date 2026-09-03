# Coinbase-vs-Binance Price Premium TREND-FOLLOWING Regime Validation

## Primary rule
> LONG-ONLY per-asset regime filter: 24h trailing mean (prior-only) of hourly (Coinbase close / Binance close - 1) premium > 0 (sustained POSITIVE premium) -> long spot, else cash. Entries/exits at next-bar open on regime flip. 0bps round-trip cost per block.

## Data sources
- Real Coinbase Exchange public hourly OHLCV (`data/coinbase_premium/{BTC,ETH}_coinbase_1h.csv.gz`, already cached from the prior contrarian study, no new fetch needed).
- Real Binance spot hourly OHLCV (`data/raw/{BTC,ETH}_1h.csv.gz`, already cached) for execution.

### BTC
- Premium coverage: 2018-01-01 00:00:00+00:00 -> 2026-07-27 23:00:00+00:00 (74957 aligned hours)
- Regime on: 59.8% of sample, 297 blocks
- Primary final (start=1.0): **4.1613**
- Cash final: **1.0000**
- Buy-and-hold final: **4.6345**
- Daily DCA final: **3.9930**
- Momentum-control final: **4.4106**
- Random-regime control final: **1.0325**
- Doubled-cost final: **1.7048**
- Best-block-excluded final: **2.2145**
- Top block % of PnL: 38.762815625671514
- Gates: {'beats_cash': True, 'beats_buy_and_hold': False, 'beats_dca': True, 'beats_momentum_control': False, 'beats_random_control': True, 'survives_doubled_cost': True, 'survives_best_block_exclusion': False, 'concentration_ok': False, 'has_holdout_blocks': True}
- Verdict: **REJECTED**

Partition breakdown:
  - {'asset': 'BTC', 'partition': 'development', 'n_blocks': 124, 'mean_block_return_pct': 1.3760274115348266}
  - {'asset': 'BTC', 'partition': 'validation_2021_2024', 'n_blocks': 97, 'mean_block_return_pct': 0.3932479183202389}
  - {'asset': 'BTC', 'partition': 'test_2024_onward', 'n_blocks': 76, 'mean_block_return_pct': 1.076898820147747}

### ETH
- Premium coverage: 2018-01-01 00:00:00+00:00 -> 2026-07-27 23:00:00+00:00 (74974 aligned hours)
- Regime on: 58.0% of sample, 357 blocks
- Primary final (start=1.0): **15.3465**
- Cash final: **1.0000**
- Buy-and-hold final: **2.5741**
- Daily DCA final: **3.4749**
- Momentum-control final: **19.7342**
- Random-regime control final: **1.4258**
- Doubled-cost final: **5.2503**
- Best-block-excluded final: **8.9749**
- Top block % of PnL: 47.75627769846093
- Gates: {'beats_cash': True, 'beats_buy_and_hold': True, 'beats_dca': True, 'beats_momentum_control': False, 'beats_random_control': True, 'survives_doubled_cost': True, 'survives_best_block_exclusion': True, 'concentration_ok': False, 'has_holdout_blocks': True}
- Verdict: **REJECTED**

Partition breakdown:
  - {'asset': 'ETH', 'partition': 'development', 'n_blocks': 161, 'mean_block_return_pct': 1.4396315473512693}
  - {'asset': 'ETH', 'partition': 'validation_2021_2024', 'n_blocks': 121, 'mean_block_return_pct': 0.5903492588733812}
  - {'asset': 'ETH', 'partition': 'test_2024_onward', 'n_blocks': 75, 'mean_block_return_pct': 1.9417639754709874}

## Overall verdict
- 0/2 assets are CANDIDATE (clear every gate)
- Per-asset verdicts: {'BTC': 'REJECTED', 'ETH': 'REJECTED'}
