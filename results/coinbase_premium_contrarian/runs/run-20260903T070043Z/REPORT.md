# Coinbase-vs-Binance Price Premium Contrarian Validation

## Primary rule
> LONG-ONLY per-asset: z-score (720h trailing, prior-only) of hourly (Coinbase close / Binance close - 1) premium <= -2.0 (rare Coinbase DISCOUNT) -> long spot at next hour's open, hold 24h, flat otherwise. 0bps round-trip cost. Non-overlapping trades.

## Data sources
- Real Coinbase Exchange public hourly OHLCV (`data/coinbase_premium/{BTC,ETH}_coinbase_1h.csv.gz`, newly fetched this run via `scripts/fetch_coinbase_premium.py`; first use of Coinbase Exchange data in this repo).
- Real Binance spot hourly OHLCV (`data/raw/{BTC,ETH}_1h.csv.gz`, already cached) for execution.

### BTC
- Premium coverage: 2018-01-01 00:00:00+00:00 -> 2026-07-27 23:00:00+00:00 (74957 aligned hours)
- Mean absolute premium: 16.14 bps
- Trades: **492**
- Primary final (start=1.0): **0.0141**
- Buy-and-hold final: **4.6345**
- Daily DCA final: **3.9930**
- Random-timing control final: **0.9321**
- Doubled-cost final: **0.0032**
- Best-trade-excluded final: **0.0209**
- Top trade % of PnL: 10.515880124532977
- Gates: {'beats_buy_and_hold': False, 'beats_dca': False, 'beats_random_control': False, 'survives_doubled_cost': False, 'survives_best_trade_exclusion': False, 'concentration_ok': True, 'has_holdout_trades': True}
- Verdict: **REJECTED**

Partition breakdown:
  - {'asset': 'BTC', 'partition': 'development', 'n_trades': 173, 'mean_trade_return_pct': -0.9613239400785731}
  - {'asset': 'BTC', 'partition': 'validation_2021_2024', 'n_trades': 176, 'mean_trade_return_pct': -0.649108237855547}
  - {'asset': 'BTC', 'partition': 'test_2024_onward', 'n_trades': 143, 'mean_trade_return_pct': -0.7384909249709195}

### ETH
- Premium coverage: 2018-01-01 00:00:00+00:00 -> 2026-07-27 23:00:00+00:00 (74974 aligned hours)
- Mean absolute premium: 16.55 bps
- Trades: **495**
- Primary final (start=1.0): **0.0107**
- Buy-and-hold final: **2.5741**
- Daily DCA final: **3.4749**
- Random-timing control final: **1.0171**
- Doubled-cost final: **0.0024**
- Best-trade-excluded final: **0.0179**
- Top trade % of PnL: 20.664359060386037
- Gates: {'beats_buy_and_hold': False, 'beats_dca': False, 'beats_random_control': False, 'survives_doubled_cost': False, 'survives_best_trade_exclusion': False, 'concentration_ok': False, 'has_holdout_trades': True}
- Verdict: **REJECTED**

Partition breakdown:
  - {'asset': 'ETH', 'partition': 'development', 'n_trades': 175, 'mean_trade_return_pct': -0.6470302273839226}
  - {'asset': 'ETH', 'partition': 'validation_2021_2024', 'n_trades': 174, 'mean_trade_return_pct': -0.8885285377636696}
  - {'asset': 'ETH', 'partition': 'test_2024_onward', 'n_trades': 146, 'mean_trade_return_pct': -0.7703128467898791}

## Overall verdict
- 0/2 assets are CANDIDATE (clear every gate)
- Per-asset verdicts: {'BTC': 'REJECTED', 'ETH': 'REJECTED'}
