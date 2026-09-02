# Retail Long/Short Ratio Extreme-Short Contrarian Validation

Run: `.venv/bin/python3 scripts/retail_ratio_contrarian_validation.py`

Artifact: `results/retail_ratio_contrarian/runs/run-20260902T045055Z/`

## Hypothesis

Binance's real `count_long_short_ratio` field (global RETAIL account
long/short ratio — every account on the exchange, dominated by
small/unsophisticated positions) is a genuinely new data field/population for
this repo, distinct from `sum_toptrader_long_short_ratio` (largest-account
"smart money" positioning, already tested as an SMA10/SMA30 structural trend
regime and REJECTED) and from `sum_open_interest` (aggregate leveraged
notional, tested 4 ways and REJECTED) and from CFTC's institutional
"Leveraged Funds" data (also REJECTED).

Classic contrarian-crowd theory: when the RETAIL account base is extremely
short-skewed (low `count_long_short_ratio`, z-score deeply negative vs its
own trailing 90-day history), retail is "wrongfooted" into a decline; price
should rebound as retail capitulation exhausts. Long-only spot, so only the
"retail extremely short → buy" half of the thesis is testable.

## Primary rule (preregistered)

- z-score of `count_long_short_ratio` vs its own prior-only rolling 90-day
  mean/std (shift(1) before rolling — no lookahead).
- Trigger: z <= -1.5.
- Entry: next day's 00:00 UTC open (1-day lag). Exit: fixed 14-day hold,
  non-overlapping.
- Costs: standard 30bps round trip.
- Universe: BTC/ETH/SOL/XRP, each restricted to its real Binance futures
  archive coverage window (BTC 2020-09-01, ETH/SOL/XRP 2021-12-01).

## Result

| Asset | Trades | Test trades | Primary final | B&H final | DCA final | Top-trade PnL share | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| BTC | 24 | 9 | 1.33x | 5.49x | 1.68x | 86.4% | FAIL |
| ETH | 31 | 15 | 3.60x | 0.40x | 0.87x | 36.0% | FAIL |
| SOL | 31 | 13 | 0.98x | 0.35x | 1.45x | -1911% | FAIL |
| XRP | 33 | 16 | 2.60x | 1.06x | 1.55x | 81.1% | FAIL |

- BTC loses outright to buy-and-hold (1.33x vs 5.49x).
- ETH/XRP beat buy-and-hold but not DCA (ETH beats DCA: 3.60x vs 0.87x — but
  fails concentration; XRP beats DCA too but also fails concentration).
- SOL's single best trade is enormous relative to tiny total net PnL
  (top-trade PnL share -1911%, i.e. the strategy is barely profitable and
  one huge trade masks an otherwise negative-PnL rule).
- **All 4 assets fail the 20% concentration cap** (36%-1911% |top trade PnL
  share|) — the same recurring failure mode as SMA200, DVOL, stablecoin-
  trend, ratio-rotation, OI-trend, top-trader-trend, CFTC-COT in this
  program.
- Zero assets had zero test-partition trades (real 2025+ trades exist on all
  4 — better data availability than most prior positioning studies), but
  this doesn't rescue the concentration failure.

## Verdict

**REJECTED** — 0/4 assets pass all preregistered gates; decisive
concentration-cap failure on all 4 assets. Do not retest this exact z-score/
threshold/hold combination on `count_long_short_ratio`; ninth consecutive
crowded-positioning-style single-asset study (after SMA200, DVOL, FGI,
stablecoin-trend, OI-trend, top-trader-trend, CFTC-COT, and this one) to fail
on the same concentration-artifact pattern. Crowded-positioning contrarian
mechanisms (retail, smart-money, institutional COT, aggregate OI) have now
all been tested as both fast event triggers and slow structural regimes on
this repo's 4-asset universe and all failed — deprioritize further variants
of this mechanism family entirely; items 1-3 in `docs/next_hypotheses.md`
remain the highest-priority untested single-asset/single-mechanism ideas.
