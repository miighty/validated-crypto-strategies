# Crypto Market Regime & Strategy Backtest — Full Validation Prompt

## Objective

Backtest **10 trading strategies** across **10 major crypto coins** over **8 years (2018–2026)** using **real exchange data only**. Identify market regimes automatically, then validate which strategy performs best in each regime for each coin. Output verified results with full metrics.

---

## Data Requirements

### Coins
BTC, ETH, SOL, BNB, XRP, ADA, DOGE, AVAX, LINK, MATIC (POL)

### Timeframes
- **Daily (1d)** — primary for regime detection and swing strategies
- **4-hour (4h)** — for shorter-term strategies (mean reversion, grid, breakout)
- **1-hour (1h)** — for market making and stat arb validation

### Data Source Priority
1. **Binance API** (spot OHLCV via `ccxt` library) — primary source
2. **Hyperliquid API** — fallback if Binance rate-limits or times out
3. If a coin wasn't listed for the full 8 years, start from its listing date

### Data Rules
- **NEVER use proxy, synthetic, or simulated data**
- **NEVER fabricate or estimate missing candles**
- All data must come from real exchange API calls
- Log the exact source, date range, and candle count for every dataset pulled
- Save all raw data to `/Users/vr/crypto-regime-backtest/data/` as CSV files named `{COIN}_{timeframe}.csv`

---

## Phase 1: Data Collection

For each coin and timeframe:
1. Connect to Binance via `ccxt` (no API key needed for public OHLCV)
2. Fetch all available historical candles from January 2018 (or listing date) to present
3. Binance limits to 1000 candles per request — paginate using `since` parameter
4. If Binance rate-limits (HTTP 429 or timeout after 30s), switch to Hyperliquid
5. Save raw OHLCV to CSV: `timestamp, open, high, low, close, volume`
6. Print summary: coin, timeframe, source exchange, start date, end date, total candles

Install dependencies:
```bash
pip install ccxt pandas numpy ta-lib matplotlib seaborn
```
If `ta-lib` fails to install (common), fall back to `pandas-ta`:
```bash
pip install pandas-ta
```

---

## Phase 2: Regime Detection

Using the **daily** data for each coin, automatically classify every trading day into one of 5 regimes:

### Regime Definitions (use ALL of these indicators together)
1. **Bull Trend** — ADX > 25 AND +DI > -DI AND price above 50-day SMA
2. **Bear Trend** — ADX > 25 AND -DI > +DI AND price below 50-day SMA
3. **Range/Chop** — ADX < 20 AND Bollinger Band width below 20-day median
4. **High Vol Expansion** — ATR(14) > 2x its 60-day moving average (breakout territory)
5. **Crash/Capitulation** — Drawdown from 30-day high > 25% AND volume spike > 2x average

### Implementation
- Compute: ADX(14), +DI(14), -DI(14), SMA(50), Bollinger Bands(20,2), ATR(14)
- Classify each day into exactly one regime (priority: Crash > High Vol > Bull/Bear > Range)
- Save regime labels to `/Users/vr/crypto-regime-backtest/regimes/{COIN}_regimes.csv`
- Print regime distribution per coin (% of days in each regime)

---

## Phase 3: Strategy Implementation

Implement each strategy with realistic assumptions:
- **Trading fees:** 0.1% per trade (taker)
- **Slippage:** 0.05% per trade
- **Starting capital:** $10,000 per strategy per coin
- **No lookahead bias** — signals use only past data
- **Position sizing:** Fixed fractional (2% risk per trade where applicable)

### Strategy Specifications

#### 1. Trend Following
- Entry: Price crosses above/below 20-day EMA, confirmed by 50-day EMA direction
- Exit: Trailing stop at 2x ATR(14)
- Timeframe: Daily

#### 2. Mean Reversion
- Entry: Price touches lower/upper Bollinger Band (20,2) AND RSI(14) < 30 or > 70
- Exit: Price returns to middle band (20-day SMA)
- Stop: 1.5x ATR below/above entry
- Timeframe: 4h

#### 3. Momentum (Cross-Sectional)
- Rank all 10 coins by 20-day return
- Long top 3, short bottom 3 (or long-only: top 3)
- Rebalance weekly
- Timeframe: Daily

#### 4. Breakout
- Entry: Price breaks above/below 20-day high/low with volume > 1.5x 20-day avg volume
- Exit: Trailing stop at 2x ATR(14)
- Timeframe: 4h

#### 5. Grid Trading
- Set grid levels at 2% intervals around current price
- 10 grid levels above and below
- Buy at each lower grid, sell at each upper grid
- Timeframe: 1h (but evaluate on daily equity curve)

#### 6. DCA (Dollar Cost Averaging)
- Buy fixed $100 worth every week regardless of price
- No selling (accumulation only)
- Compare final portfolio value vs lump sum at start
- Timeframe: Weekly

#### 7. Funding Rate Arbitrage
- When Binance/Hyperliquid perpetual funding rate > 0.05%: short perp + long spot
- When funding rate < -0.05%: long perp + short spot (or skip)
- Collect funding every 8 hours
- Timeframe: 8h
- NOTE: Use simulated funding rate data derived from price action (basis = close - SMA(7)) if real historical funding data is unavailable. CLEARLY LABEL this as simulated.

#### 8. Statistical Arbitrage
- Pairs: BTC/ETH, SOL/AVAX, LINK/MATIC, BNB/XRP, ADA/DOGE
- Compute z-score of price ratio (30-day rolling mean and std)
- Entry: z-score > 2 or < -2
- Exit: z-score returns to 0
- Stop: z-score > 3.5 or < -3.5
- Timeframe: 4h

#### 9. Market Making (Simulated)
- Place bids/asks at 0.3% spread around mid price
- Inventory limit: max 50% of capital in position
- Hedge when inventory exceeds 30% threshold
- Timeframe: 1h
- NOTE: This is a simplified simulation — real market making requires order book data

#### 10. Contrarian
- Entry: RSI(14) < 20 (buy) or > 80 (sell) on daily
- Confirm with: volume spike > 2x 20-day average
- Exit: RSI returns to 40-60 zone
- Stop: 3x ATR below/above entry
- Timeframe: Daily

---

## Phase 4: Backtesting Engine

For each strategy × each coin:
1. Run the strategy over the entire 8-year period
2. Track: every trade entry/exit, P&L, fees paid
3. Compute per-regime performance by filtering trades that opened during each regime

### Metrics to Compute (per strategy, per coin, per regime AND overall)
- **Total Return %**
- **Annualized Return %**
- **Sharpe Ratio** (risk-free rate = 0%)
- **Max Drawdown %**
- **Win Rate %**
- **Profit Factor** (gross profits / gross losses)
- **Total Trades**
- **Average Trade Duration**
- **Calmar Ratio** (annualized return / max drawdown)

Save all trade logs to: `/Users/vr/crypto-regime-backtest/results/trades/{STRATEGY}_{COIN}_trades.csv`
Save metrics to: `/Users/vr/crypto-regime-backtest/results/metrics/{STRATEGY}_{COIN}_metrics.json`

---

## Phase 5: Analysis & Output

### 5a. Master Summary Table
Create a table: rows = strategies, columns = regimes, cells = average Sharpe ratio across all coins.
Highlight the **best strategy per regime** in each cell.
Save to: `/Users/vr/crypto-regime-backtest/results/master_summary.csv`

### 5b. Per-Coin Best Strategy Table
For each coin, rank strategies by Sharpe ratio within each regime.
Save to: `/Users/vr/crypto-regime-backtest/results/per_coin_summary.csv`

### 5c. Regime Distribution Chart
Bar chart showing % of time each coin spent in each regime.
Save to: `/Users/vr/crypto-regime-backtest/charts/regime_distribution.png`

### 5d. Equity Curves
For each strategy, plot the equity curve across the full period with regime-colored background shading.
Save to: `/Users/vr/crypto-regime-backtest/charts/{STRATEGY}_equity.png`

### 5e. Strategy Correlation Matrix
Compute correlation of daily returns between all 10 strategies (averaged across coins).
Save to: `/Users/vr/crypto-regime-backtest/charts/strategy_correlation.png`

### 5f. Final Report
Generate a markdown report at `/Users/vr/crypto-regime-backtest/REPORT.md` containing:
1. Data sources used (exchange, date ranges, candle counts per coin)
2. Regime distribution summary
3. Master strategy × regime table with Sharpe ratios
4. Per-coin best strategy recommendations
5. Top 3 strategy combinations for a regime-adaptive system
6. All chart images embedded
7. Caveats and limitations

---

## Execution Notes

- This is a large computation. Work through it systematically: data first, then regimes, then one strategy at a time.
- If any single step fails, log the error, skip that coin/strategy combination, and continue with the rest.
- Use `pandas` for all data manipulation. Use `matplotlib`/`seaborn` for charts.
- Do NOT approximate or fabricate any results. If data is unavailable for a coin before its listing date, clearly note the shortened backtest period.
- Expect the full pipeline to take significant time. Use efficient pagination and caching — save intermediate results so crashed runs can resume.
- Print progress updates as you go: "Fetching BTC 1d... done (2922 candles)", "Running Trend Following on ETH... done (142 trades)", etc.
- All output folders should be created automatically if they don't exist.
