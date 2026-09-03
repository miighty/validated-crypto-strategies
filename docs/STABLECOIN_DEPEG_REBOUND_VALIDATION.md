# Stablecoin depeg contrarian rebound validation

Run artifact: `results/stablecoin_depeg_rebound/runs/run-20260903T034647Z/`

## Hypothesis

Regulated/audited stablecoins (USDC, TUSD, USDP, FDUSD) occasionally trade
below their 1.00 USD peg for hours to days during redemption friction or
banking-partner stress (e.g. USDC/SVB March 2023). Buying the discounted
stablecoin against USDT on Binance spot and holding until re-peg (or a
capped max hold) should capture this convergence after realistic round-trip
costs — a mechanically-grounded reversion distinct from every prior
sentiment/positioning "buy the panic" study in this program, and distinct
from the already-REJECTED stablecoin-supply-TREND study (which used
aggregate DefiLlama supply as a fundamental filter on BTC/ETH/SOL/XRP, never
a stablecoin's own price).

## Primary rule (preregistered)

- Universe: USDC/USDT, TUSD/USDT, USDP/USDT, FDUSD/USDT, real Binance spot
  hourly OHLCV (newly fetched this run, `data/stablecoin_depeg/*.csv.gz`).
- Signal: hourly LOW <= 0.990 (1% below peg).
- Entry: next hourly bar's open.
- Exit: first hourly close >= 0.999 (repeg), or 168h (7 day) max hold,
  whichever first.
- Cooldown: 24h after exit before a new entry.
- Costs: repo-standard 30bps round-trip.
- Baselines: cash (correct primary — a pegged asset "buy and hold" is
  mechanically ~0% too), buy-and-hold the stablecoin, seeded random-timing
  control matched on trade count and realized hold-length distribution.

## Result table

| Asset | Trades | Primary final | Doubled-cost final | Random-control final | Excl-best-trade final | Top-trade PnL share | Test-partition trades |
|---|---:|---:|---:|---:|---:|---:|---:|
| USDC | 26 | 1.1163x | 1.0325x | 0.9186x | 1.0252x | 78.0% | 2 |
| TUSD | 41 | 1.0988x | 0.9716x | 0.9006x | 1.0701x | 28.1% | 7 |
| USDP | 10 | 1.0128x | 0.9829x | 0.9703x | 0.9784x | 263.4% | 3 |
| FDUSD | 4 | 1.0388x | 1.0264x | 0.9886x | 1.0064x | 83.4% | 4 |

## Honest conclusion

> **REJECTED.** All 4 stablecoins beat cash and the random-timing control on
> the full sample, and 2/4 survive doubled costs — but this is a
> concentration artifact, not a repeatable arbitrage edge. **0/4 assets
> clear the 20% concentration cap** (top-trade PnL share 28%-263%): the
> single dominant trade on USDC and USDP is the March 2023 USDC/SVB
> depeg-to-$0.87 event, an extremely rare tail event, not a recurring
> pattern. Excluding that one trade, most remaining depeg episodes are
> shallow (0.5-1.5% below peg) and their gross per-trade return is often
> smaller than the 30bps round-trip cost — many individual trades in the
> ledger show gross returns of -0.3% to +0.3%, i.e. below or barely at the
> cost floor. Doubled costs flip TUSD and USDP net-negative outright.

## Decisive checks

- **Concentration cap:** violated on all 4 assets (28%-263% vs the 20% cap).
- **Doubled-cost check:** TUSD 0.9716x and USDP 0.9829x fall below 1.0
  (net loss); only USDC/FDUSD survive.
- **Test-partition trades:** real 2024+ holdout trades exist on all 4 assets
  (2-7/asset), so this is not a zero-holdout rejection — the mechanism has
  fired recently, it just isn't durably profitable net of costs and
  concentration.
- Real trades and depeg magnitudes were sourced entirely from Binance spot
  hourly OHLCV; no synthetic or proxied depeg data was used.

## Files

- `results/stablecoin_depeg_rebound/runs/run-20260903T034647Z/strategy_summary.csv`
- `results/stablecoin_depeg_rebound/runs/run-20260903T034647Z/partition_summary.csv`
- `results/stablecoin_depeg_rebound/runs/run-20260903T034647Z/{USDC,TUSD,USDP,FDUSD}_trades.csv`
- `results/stablecoin_depeg_rebound/runs/run-20260903T034647Z/verdict.txt`
- Real Binance spot hourly OHLCV cached: `data/stablecoin_depeg/{USDC,TUSD,USDP,FDUSD}USDT_1h.csv.gz`
