# Polymarket + Crypto Validation Findings

Run artifact: `results/polymarket_validation/run-20260807T220612Z/REPORT.md`

## Scope

This validation tested ten strategy ideas inspired by Polymarket event odds combined with crypto price action, using:

- **Binance public hourly OHLCV** already pinned in this repo for BTC, ETH, and SOL
- **Polymarket public market metadata** from the Gamma API
- **Polymarket public trade history** from the Data API, reconstructed into hourly YES-probability series

## Evidence boundary

- Crypto trade costs: **0.15% one-way** (`0.10%` fee + `0.05%` slippage), matching repo defaults
- Polymarket-native strategy cost proxy: **0.20% one-way**
- Curated event markets fetched: **9**
- Broader Polymarket universe used for native strategy sampling: **31** high-volume markets

## Final scoreboard

| Strategy | Status | Trades | Ending equity | Total return | Verdict |
|---|---|---:|---:|---:|---|
| Cross-venue disagreement | Blocked | 0 | 10000.00 | 0.00% | Not completed: Kalshi matching/candles not finished in this run |
| ETH ETF spread | Completed | 1 | 10915.43 | 9.15% | Promising but far too little sample |
| Trump policy beta | Completed | 0 | 10000.00 | 0.00% | No completed trades under current rules |
| Wick + odds confirmation | Completed | 0 | 10000.00 | 0.00% | No completed trades under current rules |
| Resolution-time decay | Completed | 0 | 10000.00 | 0.00% | No valid late-fade sample under current rules |
| Bitcoin ETF flow prediction | Completed | 0 | 10000.00 | 0.00% | No sufficient sample from discovered flow markets |
| Favorite-longshot bias | Completed | 26 | 9951.65 | -0.48% | Slight loser after cost proxy |
| Fed-cut macro beta | Completed | 9 | 9255.09 | -7.45% | Rejected |
| Odds shock catch-up | Completed | 81 | 4755.52 | -52.44% | Rejected |
| Crypto-specific lead/lag | Completed | 54 | 4072.48 | -59.28% | Rejected |

## Strategy-by-strategy interpretation

### 1) Odds shock → crypto catch-up
Rule tested: trade BTC after large 24h Polymarket repricing across major event markets when BTC had not obviously overreacted already.

**Result:** failed badly.

Why it failed:
- odds shocks often coincided with already noisy, two-way crypto moves
- simple 24h delta rules were too blunt
- many “underreaction” cases were actually wrong-sign or overfit to narrative hindsight

### 2) ETH ETF approval odds → ETH/BTC spread
Rule tested: long **ETH / short BTC** for 72h after large positive ETH ETF odds shocks above a 60% level.

**Result:** only one completed trade, but it worked well.

Interpretation:
- this is the cleanest candidate from the set
- however, one trade is not enough to call it edge
- it should be treated as **promising but unvalidated**, not approved

### 3) Trump/pro-crypto election odds → BTC
Rule tested: long BTC after positive Trump-election odds shocks once the market was already above 50%.

**Result:** no completed trades under the current gating.

Interpretation:
- the concept still makes intuitive sense
- but the specific thresholding was too restrictive in this implementation

### 4) Fed-cut odds → ETH macro beta
Rule tested: trade ETH on front-end Fed-cut probability shocks.

**Result:** negative.

Interpretation:
- the event-to-asset mapping was plausible
- the realized crypto response was too inconsistent to survive costs

### 5) Wick flush + supportive odds confirmation
Rule tested: buy violent BTC wick flushes only if supportive ETF/election/reserve odds were not simultaneously deteriorating.

**Result:** no completed trades.

Interpretation:
- the combined filters were too strict on this sample
- this idea may still be worth revisiting with looser wick thresholds or recovery triggers

### 6) Crypto-specific lead/lag
Rule tested: trade BTC/ETH/SOL directly when crypto-specific markets (BTC ETF, ETH ETF, SOL ETF, Bitcoin reserve) repriced sharply.

**Result:** strongly negative.

Interpretation:
- raw event repricing alone was not enough
- large narrative moves did not translate into reliable directional continuation

### 7) Cross-venue disagreement (Polymarket vs Kalshi)
**Status:** blocked.

Interpretation:
- Kalshi’s public API is reachable
- but exact market matching + comparable historical candle extraction were not finished in this run
- this one remains open research, not completed work

### 8) Favorite-longshot bias on Polymarket
Rule tested: 24h before resolution, buy YES favorites above 65% or buy NO against YES longshots below 35%.

**Result:** close to flat but slightly negative after the cost proxy.

Interpretation:
- there may be structure here
- but the naive implementation was not enough to clear costs

### 9) Resolution-time decay / late mispricing fade
Rule tested: fade late surges into extreme-but-not-certain probability bands shortly before resolution.

**Result:** no valid trades from the filtered universe.

Interpretation:
- either the filter was too selective or the sampled universe was too small

### 10) Bitcoin ETF flow prediction markets → BTC
Rule tested: trade BTC for 24h when pre-resolution ETF-flow odds were strongly skewed.

**Result:** no sufficient sample in the discovered flow market set.

Interpretation:
- data sourcing for these daily flow markets needs to be broadened before judging the idea

## Main conclusions

1. **Most simple event-odds follow-through rules failed.**
2. The only standout was **ETH ETF odds → ETH/BTC spread**, but the sample is too small to validate.
3. **Naive lead/lag and generic catch-up rules should be rejected** in their current form.
4. The next round should focus on **fewer, cleaner, asset-specific event mappings** rather than broad “Polymarket sentiment” trading.

## Best next candidates

If continuing this line of research, prioritize:

1. **ETH ETF odds → ETH/BTC spread**, but extend with more regulatory/ETF analogues
2. **Cross-venue disagreement**, once Kalshi matching is implemented
3. **Wick flush + odds confirmation**, with looser panic/recovery logic
4. **Bitcoin reserve / policy odds** as a slower swing filter rather than a 24h shock signal

## Files to inspect

- `results/polymarket_validation/run-20260807T220115Z/REPORT.md`
- `results/polymarket_validation/run-20260807T220115Z/strategy_summary.csv`
- `results/polymarket_validation/run-20260807T220115Z/trade_log.csv`
- `results/polymarket_validation/run-20260807T220115Z/market_metadata.csv`
- `results/polymarket_validation/run-20260807T220115Z/market_universe.csv`
