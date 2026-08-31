# Cross-Exchange (Binance vs Hyperliquid) Funding Divergence Validation

Run artifact: `results/funding_crossexchange_divergence/runs/run-20260831T002353Z/REPORT.md`

## Hypothesis

Persistent divergence between two independent exchanges' funding rates for
the same asset reflects venue-specific positioning imbalance; a large
divergence should predict the spread narrowing, tradeable as a real,
price-neutral perp-vs-perp basis trade (long the cheaper venue's perp, short
the more expensive venue's perp, equal notional).

This is mechanistically distinct from every prior funding study in this repo:
- `funding_positive_panel` / `funding_negative_panel`: single-exchange,
  unhedged directional (REJECTED).
- `funding_carry_deltaneutral`: single-exchange spot+perp hedge, timed by
  the level of one venue's own funding (REJECTED).
- `funding_carry_cross_sectional`: single-exchange, cross-sectional L/S
  ranking across coins (REJECTED).
- This study: two-exchange (Binance + Hyperliquid), perp-vs-perp, no spot
  leg, timed by the DIVERGENCE between the two venues' real funding prints.

## Data

- Binance real USD-M 8h funding history, already cached
  (`data/funding/{ASSET}_funding.csv.gz`).
- Hyperliquid real hourly funding history, fetched this run via the public
  `fundingHistory` endpoint (`https://api.hyperliquid.xyz/info`), cached at
  `data/hyperliquid_funding/{ASSET}_funding.csv.gz`. Hyperliquid's public API
  only returns history back to **2023-05-12** (BTC/ETH/SOL) / **2023-06-18**
  (XRP) — this is a materially shorter sample than Binance alone provides.
- Hourly Hyperliquid prints compounded into 8h windows aligned to each real
  Binance settlement (00:00/08:00/16:00 UTC), requiring exactly 8 available
  hourly prints per window (no partial/interpolated windows).
- No proxy or synthetic funding/price data used anywhere.

## Primary rule (preregistered)

At each matched settlement, if `|Binance_8h - Hyperliquid_8h| >= 5bps`, enter
a perp-vs-perp basis trade: long the cheaper venue's perp, short the more
expensive venue's perp, hold 1 settlement (8h), exit, reassess. Round-trip
cost: 2 legs x 2 venues at the repo's standard 15bps one-way cost.

## Result

| Asset | Overlap window | Trades | Final capital | Total return | Sharpe | Random-timing control | Verdict |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| BTC | 2023-06-08 -> 2026-07-27 | 71 | $6,865.66 | -31.34% | -41.80 | $6,525.17 | REJECTED |
| ETH | 2023-06-08 -> 2026-07-27 | 77 | $6,615.71 | -33.84% | -87.40 | $6,275.65 | REJECTED |
| SOL | 2023-06-08 -> 2026-07-27 | 174 | $4,005.27 | -59.95% | -64.80 | $3,515.04 | REJECTED |
| XRP | 2023-06-18 -> 2026-07-27 | 90 | $6,179.05 | -38.21% | -60.70 | $5,816.88 | REJECTED |

## Decisive blockers

1. **Mean absolute divergence is tiny (~1.0-1.4 bps)** across all 4 assets —
   far below the round-trip cost of a 2-venue, 2-leg basis trade (60bps at
   the repo's standard cost model). Even the (rare) >=5bps trigger events do
   not carry enough edge to clear costs.
2. **All four assets lost real capital outright** (34-60% net loss on $10,000
   starting capital), decisively worse than cash.
3. **Doubled-cost check makes it strictly worse** on all 4 assets (e.g. BTC
   $6,865.66 -> $4,475.45), confirming cost-dominance rather than a marginal
   miss.
4. **The strategy barely beats — and on SOL trails — its own seeded
   random-timing control** (same trade count/hold/costs, random direction),
   indicating the "long the cheaper venue" directional call carries little to
   no genuine predictive value once controlling for the cost drag any
   frequent basis-flipping strategy pays.
5. Walk-forward shows the loss concentrated in the first half of the sample
   (67-168 trades) with the second half nearly flat on far fewer trades (4-17)
   — consistent with the >=5bps trigger becoming rarer over time as
   Hyperliquid's market matured and its funding converged toward Binance's,
   not with a genuine but decaying edge.

## Honesty disclosures

- No cross-exchange collateral-transfer friction or exchange-specific
  liquidation risk modeled beyond the shared round-trip cost model — a real
  implementation would face additional operational risk this backtest does
  not capture.
- Hyperliquid's short public funding history (2023-06 onward) means this is
  a shorter, more recent-regime-biased sample than the repo's other funding
  studies.

## Verdict

**REJECTED — decisive across all 4 assets.** The funding divergence between
Binance and Hyperliquid is real but too small (~1bp mean) relative to the
combined 4-leg round-trip cost of a cross-exchange basis trade to produce a
tradeable edge at any of the tested thresholds/hold lengths in the
sensitivity grid. Do not retest this exact 2-venue perp-vs-perp basis
mechanism without either a fundamentally lower-cost execution path (e.g. an
exchange/product pair with materially lower combined round-trip cost than
30bps/leg-pair) or evidence of larger structural divergence on a different
exchange pair. Items 1-3 in `next_hypotheses.md` remain the highest-priority
untested single-asset/single-mechanism ideas.
