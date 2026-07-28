# Methodology and Strategy Contract

## Snapshot

- Window: `2018-01-01T00:00:00Z` to `2026-07-28T00:00:00Z` exclusive.
- Assets: BTC, ETH, SOL, BNB, XRP, ADA, DOGE, AVAX, LINK, and POL (MATIC history followed by POL history, with the exchange migration gap preserved).
- Frequencies: 1d, 4h, and 1h spot candles; real 8-hour-like USD-M funding observations.
- Source: public Binance endpoints. No API keys are read.
- Missing pre-listing history and exchange gaps are retained. No candle is imputed.

## Regimes

Daily finalized bars compute ADX(14), +DI/-DI(14), SMA(50), Bollinger Bands(20,2), ATR(14), 30-day drawdown, and volume averages. Priority is:

1. Crash/Capitulation: drawdown from 30-day high below -25% and volume above 2× its 20-day mean.
2. High Vol Expansion: ATR(14) above 2× its 60-day mean.
3. Bull Trend: ADX above 25, +DI above -DI, and close above SMA(50).
4. Bear Trend: ADX above 25, -DI above +DI, and close below SMA(50).
5. Range/Chop: residual class required to give each warmed-up day one label.

`range_rule_matched=true` separately records days satisfying the narrow requested condition: ADX below 20 and Bollinger width below its 20-day median. A daily label becomes usable only after that daily candle closes.

## Strategies

1. **Trend following (1d):** EMA(20) cross in the direction of EMA(50), with a 2×ATR trailing exit and symmetric long/short rules.
2. **Mean reversion (4h):** Bollinger touch plus RSI below 30/above 70, exit at the middle band, 1.5×ATR stop.
3. **Cross-sectional momentum (1d):** 20-day return ranks, weekly long top three/short bottom three, six equal-weight legs.
4. **Breakout (4h):** break of the prior 20-bar high/low with volume above 1.5× its prior 20-bar mean, 2×ATR trailing exit.
5. **Grid (1h):** at each UTC day boundary, center ten 2% levels each side on the prior finalized daily close; target exposure changes by 0.1 per crossed level and is capped at ±1.
6. **DCA (1d):** spend $100 at the first available bar of each ISO week from fixed $10,000 starting cash until depleted; fees and slippage reduce acquired units; no sale.
7. **Funding arbitrage:** when the absolute real funding rate exceeds 0.05%, hold the corresponding delta-neutral spot/perpetual direction. Funding is real; entry/exit charges two legs. This is **preliminary** because basis, borrow, collateral, margin, and liquidation are absent.
8. **Statistical arbitrage (4h):** requested pairs, 30-day log-price-ratio z-score; enter at ±2, exit at zero, stop at ±3.5, equal notional legs.
9. **Market making:** fully specified by the original prompt but **not validated**. OHLCV cannot prove bid/ask fills, queue priority, inventory path, adverse selection, or hedge execution. Historical L2/order-event data is required.
10. **Contrarian (1d):** RSI below 20/above 80 plus volume above 2× its 20-day mean, exit in RSI 40–60, 3×ATR stop.

## Backtest semantics

- A signal calculated on bar `t` first changes position at bar `t+1` open.
- Returns are open-to-next-open, so no signal uses its own execution bar's future high, low, or close.
- Turnover cost is `abs(new_position - old_position) × 0.15%`; a full long-to-short reversal costs two one-way changes.
- Metrics include total and annualized return, Sharpe (zero risk-free rate), maximum drawdown, win rate, profit factor, trade count, average duration, and Calmar.
- Per-regime metrics condition returns on the regime known at execution time. They are descriptive and in-sample.

## Validation ladder still required before a stronger claim

1. Freeze hypotheses and parameter choices in a trial ledger.
2. Use purged walk-forward folds with embargo appropriate to holding period.
3. Reserve a sealed time holdout that cannot influence strategy selection.
4. Re-run at doubled costs and asset-specific spread/impact models.
5. Test point-in-time universe membership to remove survivorship bias.
6. Apply block bootstrap confidence intervals and multiple-testing corrections.
7. Require every added filter to beat its immediate parent on identical eligible events.
8. Only then consider an isolated paper phase with a global execution kill switch.
