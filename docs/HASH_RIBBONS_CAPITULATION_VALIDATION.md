# Bitcoin Hash Ribbons Miner-Capitulation-Recovery Validation

EXP-2026-09-02-HASHRIBBONS-001

Run: `.venv/bin/python3 scripts/hash_ribbons_capitulation_validation.py`

## Hypothesis (preregistered)

The classic "Hash Ribbons" indicator (Charles Edwards / Capriole Investments)
tracks BTC network hashrate 30d SMA vs 60d SMA. When the fast SMA crosses
below the slow SMA, unprofitable miners are capitulating (shutting down
rigs) -- a period of maximum seller exhaustion. When the fast SMA crosses
back above the slow SMA ("recovery"), forced-selling pressure has ended --
the classic buy signal. Genuinely new data source for this repo (real
Blockchain.com public network hashrate API, first use here) and new
mechanism (miner production-cost capitulation, distinct from every prior
sentiment/positioning/calendar/trend study).

## Data (real, no proxy/synthetic inputs)

- Real Blockchain.com public `charts/hash-rate` API, daily, full history
  2009-01-03 through 2026-09-01 (6,441 rows, newly fetched and cached this
  run: `data/hashrate/btc_hashrate_1d.csv.gz`).
- Real Binance spot BTC/USDT daily OHLCV (already cached, `data/raw/BTC_1d.csv.gz`).
- BTC-only by construction -- hashrate is a Bitcoin-specific PoW
  security-budget metric; ETH is PoS (no hashrate since the 2022 Merge),
  SOL/XRP are not PoW. No proxy fabricated for the other three assets,
  consistent with this program's Deribit-DVOL precedent (also necessarily
  BTC/ETH-only for the same honest-data-availability reason).

## Design

- Entry: buy at next daily open on the first day the 30d hashrate SMA
  crosses back above the 60d SMA after a below-state (recovery cross-up),
  computed with `shift(1)` (no lookahead).
- Exit: fixed 90-day hold, non-overlapping (new signals ignored while in
  position).
- Costs: repo-standard 30bps round-trip.
- Benchmarks: BTC buy-and-hold, BTC daily DCA, seeded random-timing control
  (same trade count / 90-day hold).

## Result

| Strategy | Final USD | Trades |
| --- | ---: | ---: |
| Hash Ribbons recovery (primary) | $42,865 | 15 |
| BTC buy-and-hold | $46,414 | 1 |
| BTC daily DCA | $40,002 | 3,130 |
| Seeded random-timing control | $7,695 | 15 |
| Doubled-cost primary | $41,910 | 15 |
| Best-trade-excluded primary | $16,937 | 14 |
| 1-day execution-delay primary | $46,974 | 15 |

- 29 recovery cross-up signals fired over 2018-2026; 15 non-overlapping
  trades executed (later signals suppressed while already in a position).
- 6 real holdout trades (2024 onward) -- adequate out-of-sample sample.
- **Top-trade PnL share: 69.5%** -- decisively fails the 20% concentration
  cap; a single recovery trade (the 2019 post-capitulation rally) dominates
  the entire strategy's PnL. Excluding it drops the strategy to $16,937,
  far below both BTC buy-and-hold and DCA.
- Walk-forward: first-half Sharpe 1.24 vs second-half 0.66 -- some decay,
  not catastrophic on its own.
- Monte Carlo bootstrap p=0.222 -- not significant.
- Deflated Sharpe p=0.744 (n_trials=100, program's approximate true search
  size) -- fails decisively.
- Beats BTC DCA and the random-timing control, but **loses to plain BTC
  buy-and-hold** ($42,865 vs $46,414).

## Decisive blockers

1. **Loses outright to BTC buy-and-hold** -- the primary preregistered
   rejection gate.
2. **Concentration cap violated** (69.5% of total PnL from one trade) --
   same failure signature as nearly every other single-asset event-trigger
   study in this program (SMA200, DVOL, FGI, CFTC-COT, OI-trend,
   top-trader-trend, retail-ratio).
3. **Fails both statistical-significance gates** (MC p=0.222, DSR p=0.744).

## Verdict

**REJECTED** (decisive -- loses to buy-and-hold, concentration cap violated,
fails MC and DSR significance). The classic Hash Ribbons "buy the miner
capitulation recovery" thesis does not translate into a tradeable BTC spot
edge at a 30d/60d SMA cross-up with a fixed 90-day hold; its apparent value
over cash/DCA is driven almost entirely by a single 2019 recovery trade, the
same concentration-artifact pattern as this program's SMA200 trend-following
and DVOL/FGI/positioning-extreme rejections.

## Files

- `results/hash_ribbons_capitulation/runs/run-20260902T080852Z/strategy_summary.csv`
- `results/hash_ribbons_capitulation/runs/run-20260902T080852Z/trades.csv`
- `results/hash_ribbons_capitulation/runs/run-20260902T080852Z/partition_summary.csv`
- `results/hash_ribbons_capitulation/runs/run-20260902T080852Z/verdict.txt`
- `data/hashrate/btc_hashrate_1d.csv.gz` (real Blockchain.com data cache)
- `scripts/hash_ribbons_capitulation_validation.py`
