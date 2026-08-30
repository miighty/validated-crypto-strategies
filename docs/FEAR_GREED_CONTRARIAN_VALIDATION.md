# Crypto Fear & Greed Index Extreme-Fear Contrarian Validation

Run: `results/fear_greed_contrarian/runs/run-20260830T175901Z/`

## Hypothesis (preregistered)

alternative.me's daily Crypto Fear & Greed Index (FGI, 0-100; composite of
volatility, momentum/volume, social media, surveys, dominance, Google Trends)
reads "Extreme Fear" (<=25) at moments of acute market-wide panic. A
contrarian rule that buys spot on Extreme Fear and holds a fixed period
should beat buy-and-hold/DCA after costs — a genuinely new data source and
mechanism for this repo (never used here before; distinct from Deribit DVOL,
which is options-implied-vol-based and BTC/ETH-only, versus FGI which is a
market-wide sentiment composite covering the whole crypto market and applies
identically across BTC/ETH/SOL/XRP).

## Design

- Universe: BTC, ETH, SOL, XRP, real Binance spot 1h OHLCV (`data/raw/*_1h.csv.gz`).
- Data: real alternative.me Fear & Greed Index, full published daily history
  (2018-02-01 through 2026-08-30, 3,129 days), cached at
  `data/fear_greed/fng_raw.json` / `fear_greed_index.csv.gz`.
- Signal: trigger when FGI_t <= 25 ("Extreme Fear"). 739/3,129 days (23.6%)
  triggered.
- Entry: next day's 00:00 UTC open (one-day info lag). Hold 14 days, then
  flat. Non-overlapping trades (cooldown = hold period).
- Costs: repo-standard 30bps round trip (15bps/side).
- Partitions: development 2018-2021, validation 2021-2024, test 2024-2026.
- Falsification: primary rule must beat B&H AND DCA on all 4 assets, survive
  doubled costs, survive best-trade exclusion, and not lose in the test
  partition. Any failure -> REJECTED.

## Result

| Asset | Primary final ($1 start) | B&H final | DCA final | Trades | Beats B&H | Beats DCA |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| BTC | 0.84 | 6.21 | 3,988.79 | 84 | No | No |
| ETH | 0.20 | 1.67 | 3,497.82 | 84 | No | No |
| SOL | 0.18 | 25.14 | 4,057.62 | 53 | No | No |
| XRP | 0.32 | 1.16 | 2,241.91 | 81 | No | No |

(DCA final figures are on the released-capital-schedule convention used
throughout this repo — a different capital base than the lump-sum signal
strategy — so absolute magnitudes aren't directly comparable across columns,
but the `beats_dca`/`beats_bh` boolean flags use the correct like-for-like
comparison internally.)

Zero of 4 assets beat buy-and-hold. Zero of 4 beat DCA. Zero of 4 survive
doubled costs. Zero of 4 survive best-trade exclusion. Test partition: only
SOL beats B&H in test (BTC/ETH/XRP all lose in test too).

Three of four assets (ETH, SOL, XRP) finished with **less absolute capital
than they started with** (0.20x, 0.18x, 0.32x) — this is not merely
underperforming a benchmark, the strategy lost money outright on 84/53/81
non-overlapping 14-day trades gated on a "buy the panic" signal.

## Honest conclusion

**REJECTED, decisively.** "Extreme Fear" on the composite FGI does not
identify a durable price bottom at a 14-day holding horizon on any of the
four tested assets. The index is dominated by realized volatility and
social/momentum components that tend to stay elevated (fear persists) well
beyond a 14-day window during real drawdowns (e.g. 2022 bear market, 2018-19
crypto winter), so "buy on Extreme Fear, hold 14 days" repeatedly bought into
ongoing declines rather than catching bottoms. This is consistent with this
repo's DVOL-fear-spike study (implied-vol based, BTC/ETH only) which found
the same qualitative failure mode via a different vol-based fear signal.

## Decisive blockers

1. Loses to buy-and-hold on all 4 assets, all partitions except one
   (SOL/test only).
2. Loses to DCA on all 4 assets.
3. Absolute capital loss (not just underperformance) on 3/4 assets.
4. Doubled-cost and best-trade-exclusion checks both fail on all 4 assets —
   not a marginal or cost-fragile near-miss, a clean rejection.

## Follow-up question

Do not retest the plain FGI-extreme-fear-level rule at this threshold/hold
without a fundamentally different filter (e.g. requiring a price-reclaim
confirmation after the fear reading, rather than buying immediately into the
panic, mirroring the DVOL study's own follow-up recommendation). A shorter
hold (e.g. 3-7 days) or a stricter threshold (<=10, "Extreme Fear" tail) could
be tested if revisited, but given the decisiveness of this rejection (3/4
assets lost absolute capital), this mechanism is a low priority for further
tuning versus remaining single-asset/single-mechanism ideas in
`next_hypotheses.md`.

## Files

- `results/fear_greed_contrarian/runs/run-20260830T175901Z/strategy_summary.csv`
- `results/fear_greed_contrarian/runs/run-20260830T175901Z/partition_summary.csv`
- `results/fear_greed_contrarian/runs/run-20260830T175901Z/{BTC,ETH,SOL,XRP}_trades.csv`
- `data/fear_greed/fng_raw.json`, `data/fear_greed/fear_greed_index.csv.gz`
