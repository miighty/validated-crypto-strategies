# Order-Book Depth Confirmed Daily Breakout Validation

Run artifact: `results/breakout_orderbook_confirmation/runs/run-20260904T174315Z/REPORT.md`

## Hypothesis

Follow-up on two existing ingredients already tested separately in this repo:

- parent system: plain daily 20-day-high / 10-day-low breakout
- new microstructure input: real Binance USD-M order-book depth imbalance

Preregistered rule:

- breakout trigger: daily close > prior-only rolling 20-day high
- confirmation filter: same completed day's order-book imbalance z-score >= +0.5 versus its own prior-only trailing 90-day history
- entry: next daily open
- exit: next daily open after first close < prior-only rolling 10-day low
- costs: 30bps round trip
- universe: BTC, ETH, SOL, XRP
- comparison window: identical 2023-01-01+ overlap where real depth archive exists

Threshold choice was fixed from signal-count viability only:

- z >= +1.5 left too few combined signals in the 2023+ archive to evaluate fairly
- z >= +0.5 preserved 8-17 executed trades per asset without peeking at returns

## Result table

| Asset | Trades | Filtered final | Unfiltered breakout | Buy-and-hold | DCA | Random control | Top trade % PnL | Verdict |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| BTC | 10 | 1.64x | 3.43x | 3.85x | 1.25x | 1.60x | 59.6% | REJECTED |
| ETH | 17 | 0.85x | 1.11x | 1.58x | 0.81x | 1.60x | -173.6% | REJECTED |
| SOL | 11 | 2.68x | 11.36x | 7.43x | 1.29x | 1.55x | 65.6% | REJECTED |
| XRP | 8 | 3.92x | 3.50x | 3.14x | 1.35x | 0.72x | 108.1% | REJECTED |

## Honest conclusion

**REJECTED, decisively, 0/4 assets.**

- Primary falsification criterion failed on 3/4 assets:
  - BTC 1.64x vs unfiltered breakout 3.43x
  - ETH 0.85x vs 1.11x
  - SOL 2.68x vs 11.36x
- XRP is the only asset where the filter beats the parent control, but it still fails the concentration gate badly:
  - 108.1% of total PnL came from a single trade
  - best-trade exclusion drops final capital below start in the full run artifact
- Statistical validation also fails across the board:
  - Monte Carlo p-values 0.2605-0.9440
  - Deflated Sharpe p-values 0.8040-0.9952
- The filter removed more profitable breakout entries than noisy ones:
  - raw combined signals fell to 17/35/29/20 from 185/157/157/103 raw breakouts on BTC/ETH/SOL/XRP

## Files

- `docs/ORDERBOOK_BREAKOUT_CONFIRMATION_VALIDATION.md`
- `results/breakout_orderbook_confirmation/runs/run-20260904T174315Z/REPORT.md`
- `results/breakout_orderbook_confirmation/runs/run-20260904T174315Z/summary.csv`
- `results/breakout_orderbook_confirmation/runs/run-20260904T174315Z/{BTC,ETH,SOL,XRP}_filtered_trades.csv`
- `results/breakout_orderbook_confirmation/runs/run-20260904T174315Z/{BTC,ETH,SOL,XRP}_control_trades.csv`
- `results/breakout_orderbook_confirmation/runs/run-20260904T174315Z/{BTC,ETH,SOL,XRP}_signal_frame.csv`
- `src/crypto_regime_backtest/breakout_orderbook_confirmation_validation.py`
- `tests/test_breakout_orderbook_confirmation_validation.py`
