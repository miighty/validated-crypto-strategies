# VIX Fear-Spike Crypto Rebound Validation

- **Experiment ID:** EXP-2026-09-06-VIXFEAR-001
- **Verdict:** REJECTED
- **Primary rule:** CBOE/FRED VIXCLS daily close z-score >= +2.0 vs prior-only 60-trading-day baseline; buy BTC/ETH/SOL/XRP spot at the next daily open; hold 7 days; 30 bps round-trip cost; non-overlapping trades.
- **Why new:** first use of real external TradFi volatility data (VIXCLS); distinct from Deribit DVOL, Fear & Greed, DXY, FOMC calendar, and all crypto-native flow/positioning studies.
- **Real data:** FRED VIXCLS cached at `data/macro_vix/vixcls_1d.csv.gz` (1991-11-26 to 2026-07-27, 54 raw trigger days before cooldown) plus cached Binance spot daily OHLCV.

## Results

| Asset | Trades | Final | B&H | DCA | Random | 2x cost | +1d delay | 2024+ final vs B&H | Sharpe | MaxDD | Top trade PnL | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| BTC | 22 | $11,573.70 | $46,344.78 | $39,941.66 | $5,265.19 | $10,834.49 | $11,416.59 | $9,012.58 vs $15,032.99 (12 trades) | 0.21 | -21.2% | 97.5% | Rejected |
| ETH | 22 | $8,264.22 | $25,741.27 | $34,753.86 | $7,913.71 | $7,736.39 | $8,600.91 | $7,210.25 vs $8,268.92 (12 trades) | -0.08 | -36.1% | 71.5% | Rejected |
| SOL | 22 | $17,063.19 | $259,570.99 | $40,615.95 | $10,187.73 | $15,973.37 | $17,280.69 | $11,616.75 vs $7,272.68 (12 trades) | 0.50 | -30.1% | 40.2% | Rejected |
| XRP | 22 | $12,689.55 | $21,258.13 | $22,385.07 | $9,908.20 | $11,879.07 | $11,670.37 | $11,176.34 vs $17,268.99 (12 trades) | 0.26 | -22.3% | 46.5% | Rejected |

## Decisive checks

- Majority benchmark gate failed: 0/4 assets beat buy-and-hold; 0/4 beat DCA.
- Cost/latency robustness failed: no asset both beats benchmarks and remains robust under doubled costs and an extra 1-day delay.
- Concentration failed on every asset: the largest winning trade exceeded the 20% absolute-PnL cap on all four assets.
- Test partition failed the majority gate: only SOL beat buy-and-hold in 2024+ out-of-sample scoring; BTC/ETH/XRP lost.

## Conclusion

- External VIX fear spikes do not provide a standalone crypto rebound edge under the preregistered rule.
- The result joins prior fear/panic timing rejections: raw stress spikes tend to occur during continuing drawdowns, and sparse winners are too concentrated to validate.
