# CFTC COT Leveraged-Fund Positioning Extreme Validation

Run artifact: `results/cftc_cot_positioning_extreme/runs/run-20260901T222620Z/`

## Hypothesis

CME-regulated futures COT data (weekly, public, first use in this repo — distinct
from every prior Binance/Hyperliquid/Bybit perp funding+OI study) discloses
"Leveraged Funds" net positioning. Classic TradFi COT contrarian thesis: when
Leveraged Funds are extremely net-short vs their own trailing history (52-week
z-score <= -1.5), the position is crowded and vulnerable to a short-covering
squeeze — buy spot, hold 14 days, then flat.

## Data

- Real CFTC Socrata public API (`publicreporting.cftc.gov/resource/gpe5-46if.json`),
  weekly "Legacy Futures Only" report.
- BTC: CME "BITCOIN" futures, 438 weekly reports, 2018-04-10 → 2026-08-25.
- ETH: CME "ETHER CASH SETTLED" futures, 282 weekly reports, 2021-04-06 → 2026-08-25.
- Real Binance spot 1h OHLCV (already cached) for execution.
- Publication lag modeled explicitly: report_date + 4 calendar days (Tuesday
  positions → Friday release) before signal is tradeable.
- No proxy data — SOL/XRP excluded (CME lists no regulated futures for either).

## Result

| Asset | Trades | Primary final | B&H final | DCA final | Best-trade PnL share | Test partition |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| BTC | 40 | 1.92x | 8.06x | 3.91x | 61.2% | LOSES (0.87x vs 1.50x B&H) |
| ETH | 21 | 1.28x | 0.92x | 0.84x | 121.8% (net-negative ex-best-trade) | development/test win, validation loses |

## Decisive blockers

1. **BTC loses to buy-and-hold by 4.2x** (1.92x vs 8.06x) and to DCA (1.92x vs 3.91x) — the contrarian short-covering thesis does not hold on the asset with the deepest, most reliable real history (438 weeks).
2. **BTC fails the test partition** (2024-onward): 0.87x vs buy-and-hold 1.50x.
3. **Both assets fail the concentration cap** (20% max): BTC's single best trade is 61.2% of total strategy PnL; ETH's best-trade-exclusion result is net-negative on its own PnL (121.8% share), meaning the entire apparent ETH edge is a single trade.
4. **ETH's headline win is partition-inconsistent** — beats B&H in development and test, but loses decisively in validation (0.88x vs 2.88x), the classic look-then-leap warning sign already seen in this program's SMA/DVOL/FGI rejections.
5. Doubled-cost check fails on BTC (1.70x, still under B&H).

## Verdict

**REJECTED** (decisive on BTC: loses outright to B&H/DCA/test-partition; both assets fail the concentration cap). The classic COT "leveraged funds crowded short → squeeze" contrarian read does not translate into a tradeable crypto spot edge at 52-week z-score / -1.5 threshold / 14-day hold, joining this program's other "buy the panic/crowded positioning" rejections (DVOL fear-spike, FGI extreme-fear, crowded-perp-unwind).

## Files

- `results/cftc_cot_positioning_extreme/runs/run-20260901T222620Z/strategy_summary.csv`
- `results/cftc_cot_positioning_extreme/runs/run-20260901T222620Z/partition_summary.csv`
- `results/cftc_cot_positioning_extreme/runs/run-20260901T222620Z/{BTC,ETH}_trades.csv`
- `results/cftc_cot_positioning_extreme/runs/run-20260901T222620Z/verdict.txt`
- `data/cftc_cot/cme_{btc,eth}_cot_raw.json` (real CFTC data cache)
- `scripts/cftc_cot_positioning_extreme_validation.py`
