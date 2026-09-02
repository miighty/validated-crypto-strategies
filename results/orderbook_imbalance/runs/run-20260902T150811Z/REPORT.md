# Order-Book Depth Imbalance (Contrarian-Liquidity) Validation

## Primary rule
> LONG-ONLY per-asset: z-score (90d trailing, prior-only) of daily bid-vs-ask order-book notional-depth imbalance (1-2% from mid) >= +1.5 -> long spot at next day's open, hold 7 days, flat otherwise. 0bps round-trip cost. Non-overlapping trades.

## Data sources
- Real Binance USD-M futures order-book depth archive (`data/orderbook_depth/*_depth_imbalance_1d.csv.gz`, newly fetched this run via `scripts/fetch_orderbook_depth.py`; first use of L2 order-book data in this repo), coverage 2023-01-01 through 2026-09-01.
- Real Binance spot daily OHLCV (`data/raw/*_1d.csv.gz`, already cached).

### BTC
- Trades: **51**
- Primary final (start=1.0): **0.9439**
- Buy-and-hold final: **3.8427**
- Daily DCA final: **1.2439**
- Random-timing control final: **1.1040**
- Doubled-cost final: **0.8086**
- Best-trade-excluded final: **0.8208**
- Top trade % of PnL: 271.64349314770607
- Gates: {'beats_buy_and_hold': False, 'beats_dca': False, 'beats_random_control': False, 'survives_doubled_cost': False, 'survives_best_trade_exclusion': False, 'concentration_ok': False, 'has_holdout_trades': True}
- Verdict: **REJECTED**

Partition breakdown:
  - {'asset': 'BTC', 'partition': 'development', 'n_trades': 12, 'mean_trade_return_pct': -1.8009912731530315}
  - {'asset': 'BTC', 'partition': 'validation_2024', 'n_trades': 19, 'mean_trade_return_pct': 2.856571432427347}
  - {'asset': 'BTC', 'partition': 'test_2025_onward', 'n_trades': 20, 'mean_trade_return_pct': -1.4592124792552696}

### ETH
- Trades: **47**
- Primary final (start=1.0): **2.3632**
- Buy-and-hold final: **1.5775**
- Daily DCA final: **0.8090**
- Random-timing control final: **1.3434**
- Doubled-cost final: **2.0520**
- Best-trade-excluded final: **1.9406**
- Top trade % of PnL: 23.85799848757951
- Gates: {'beats_buy_and_hold': True, 'beats_dca': True, 'beats_random_control': True, 'survives_doubled_cost': True, 'survives_best_trade_exclusion': True, 'concentration_ok': False, 'has_holdout_trades': True}
- Verdict: **REJECTED**

Partition breakdown:
  - {'asset': 'ETH', 'partition': 'development', 'n_trades': 16, 'mean_trade_return_pct': 1.1235544734427623}
  - {'asset': 'ETH', 'partition': 'validation_2024', 'n_trades': 15, 'mean_trade_return_pct': 0.4534235185999292}
  - {'asset': 'ETH', 'partition': 'test_2025_onward', 'n_trades': 16, 'mean_trade_return_pct': 4.889185396173957}

### SOL
- Trades: **50**
- Primary final (start=1.0): **0.6689**
- Buy-and-hold final: **7.4200**
- Daily DCA final: **1.2839**
- Random-timing control final: **0.5544**
- Doubled-cost final: **0.5748**
- Best-trade-excluded final: **0.4926**
- Top trade % of PnL: -67.78659509234606
- Gates: {'beats_buy_and_hold': False, 'beats_dca': False, 'beats_random_control': True, 'survives_doubled_cost': False, 'survives_best_trade_exclusion': False, 'concentration_ok': False, 'has_holdout_trades': True}
- Verdict: **REJECTED**

Partition breakdown:
  - {'asset': 'SOL', 'partition': 'development', 'n_trades': 16, 'mean_trade_return_pct': -0.30747853622400745}
  - {'asset': 'SOL', 'partition': 'validation_2024', 'n_trades': 16, 'mean_trade_return_pct': 2.6663022983276656}
  - {'asset': 'SOL', 'partition': 'test_2025_onward', 'n_trades': 18, 'mean_trade_return_pct': -2.4961231959716907}

### XRP
- Trades: **46**
- Primary final (start=1.0): **0.4745**
- Buy-and-hold final: **3.1363**
- Daily DCA final: **1.3463**
- Random-timing control final: **0.6611**
- Doubled-cost final: **0.4127**
- Best-trade-excluded final: **0.2959**
- Top trade % of PnL: -61.794836759251304
- Gates: {'beats_buy_and_hold': False, 'beats_dca': False, 'beats_random_control': False, 'survives_doubled_cost': False, 'survives_best_trade_exclusion': False, 'concentration_ok': False, 'has_holdout_trades': True}
- Verdict: **REJECTED**

Partition breakdown:
  - {'asset': 'XRP', 'partition': 'development', 'n_trades': 15, 'mean_trade_return_pct': -1.9229249015086565}
  - {'asset': 'XRP', 'partition': 'validation_2024', 'n_trades': 21, 'mean_trade_return_pct': 1.9415530689638991}
  - {'asset': 'XRP', 'partition': 'test_2025_onward', 'n_trades': 10, 'mean_trade_return_pct': -5.515552529923359}

## Overall verdict
- 0/4 assets are CANDIDATE (clear every gate)
- Per-asset verdicts: {'BTC': 'REJECTED', 'ETH': 'REJECTED', 'SOL': 'REJECTED', 'XRP': 'REJECTED'}
