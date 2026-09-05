# Taker-Flow Cross-Sectional Ranking Validation

Verdict: **REJECTED**.

## Preregistered rule

- Each Monday 00:00 UTC, rank BTC/ETH/SOL/XRP by the prior-only 7-day mean of real Binance spot taker-buy volume ratio. Allocate 100% to the highest-ranked asset at that day's open, rebalance weekly, and deduct 15 bps one-way cost on each entry/exit/switch. No same-bar signal execution.
- Signal data: real Binance spot hourly klines `taker_buy_base_volume / volume`, aggregated to daily; no synthetic/proxy flow data.
- Lookahead guard: score uses a `shift(1)` prior-only 7-day mean; execution is at the next weekly rebalance open.
- First-pass delay gate: rerun with one additional daily signal delay.

## Decisive results

- Primary final capital: $8,809.96, Sharpe 0.42, max DD -93.1%.
- Best required buy-and-hold benchmark: buy_hold_SOL $487,862.38; primary trails by 0.02x.
- Seeded random same-cadence control: $18,500.98, Sharpe 0.56; primary trails random by 0.48x.
- Price-momentum top-1 control: $2,040,504.92, Sharpe 1.46; primary trails momentum by 0.00x.
- Concentration: top weekly block = 490.1% of net PnL; cap is 20%.

## Strategy comparison

| strategy | final_capital | total_return_pct | sharpe | max_drawdown_pct | n_rebalances | top_block_pnl_share_pct | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| buy_hold_BTC | 21795.7704 | 115.2484 | 0.5266 | -76.6293 | 1 | 100.0000 | nan |
| buy_hold_ETH | 25396.8730 | 156.9708 | 0.6060 | -79.3025 | 1 | 100.0000 | nan |
| buy_hold_SOL | 487862.3815 | 3901.9138 | 1.1497 | -96.2699 | 1 | 100.0000 | nan |
| buy_hold_XRP | 48548.9639 | 349.5058 | 0.7380 | -83.2396 | 1 | 100.0000 | nan |
| equal_weight_4asset_buy_hold | 145900.9972 | 1257.2094 | 0.9720 | -94.5058 | 1 | 100.0000 | nan |
| taker_flow_cross_sectional_top1 | 8809.9638 | -11.9004 | 0.4223 | -93.0596 | 290 | 490.1055 | REJECTED |
| taker_flow_cross_sectional_top1_delay1d | 4140.0151 | -58.5998 | 0.2923 | -95.8280 | 290 | -188.4576 | nan |
| price_momentum_top1_weekly | 2040504.9231 | 20305.0492 | 1.4589 | -68.9293 | 290 | 34.4745 | nan |
| seeded_random_top1_weekly | 18500.9757 | 85.0098 | 0.5597 | -80.2809 | 290 | 93.9826 | nan |

## Conclusion

- Reject: the taker-flow rank signal does not beat a seeded random allocator, a price-momentum allocator, or the stronger buy-and-hold benchmarks, and it violates the concentration cap.
