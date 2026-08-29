# Cross-Sectional Funding-Rate Carry (Dollar-Neutral L/S) Validation

EXP-2026-08-29-FUNDCARRY-001

Run: `.venv/bin/python3 scripts/funding_carry_cross_sectional.py`

## Hypothesis (preregistered)

Distinct from the already-rejected single-asset directional funding studies
(`FUNDING_POSITIVE_PANEL_VALIDATION.md`, `FUNDING_NEGATIVE_PANEL_VALIDATION.md`,
which tested long-spot timing off extreme funding prints), this is the
standard **dollar-neutral cross-sectional funding carry trade**: rank a
10-coin universe by real Binance funding rate each settlement, go long the
bottom tercile (most negative funding — shorts pay longs) and short the top
tercile (most positive funding — longs pay shorts), equal-weighted, legs
equal in gross size (net market exposure ~0).

## Data

- Real Binance USD-M funding rate history, 10 coins (BTC, ETH, SOL, XRP, BNB,
  ADA, DOGE, AVAX, LINK, POL), `data/funding/*.csv.gz`.
- Real Binance spot hourly closes for leg price returns, `data/raw/*_1h.csv.gz`.
- Window: 2021-01-01 through 2026-07-27 (all 10 coins have funding history by
  the start date). 8,223 funding timestamps, median 10/10 coins valid per print.

## Design

- Two rebalance frequencies tested: every funding print (8h) and daily
  (every 3rd print), to see whether lower turnover fixes the cost problem.
- Cost: repo-standard 30bps round-trip, charged on the turnover fraction of
  gross notional that changes membership each rebalance.
- Control: seeded random-ranking L/S with identical leg sizes/turnover/cost
  structure, to isolate whether the funding-based ranking itself adds value
  over a structurally identical randomly-ranked carry sleeve.
- Benchmarks: cash, BTC/ETH/SOL/XRP buy-and-hold, equal-weight-10 buy-and-hold.

## Result

| Strategy | Final USD | Trades | Sharpe | Verdict |
| --- | ---: | ---: | ---: | --- |
| Funding-carry L/S, 8h rebalance | 26.83 | 6,102 | -3.87 | Rejected |
| Random-ranking L/S control, 8h | 0.01 | 6,102 | -9.79 | Baseline |
| Funding-carry L/S, daily rebalance | 5,066.58 | 2,032 | -0.12 | Rejected |
| Random-ranking L/S control, daily | 344.73 | 2,032 | -1.26 | Baseline |
| Cash | 10,000.00 | 0 | n/a | Baseline |
| Equal-weight 10-asset buy-and-hold | 95,543.36 | 1 | 0.90 | Baseline |
| BTC buy-and-hold | 21,988.47 | 1 | 0.53 | Baseline |
| ETH buy-and-hold | 25,781.33 | 1 | 0.61 | Baseline |
| SOL buy-and-hold | 480,507.71 | 1 | 1.18 | Baseline |
| XRP buy-and-hold | 48,104.86 | 1 | 0.78 | Baseline |

## Verdict: REJECTED (both frequencies)

- Beats the random-ranking control at both frequencies (8h: $26.83 vs $0.01;
  daily: $5,066.58 vs $344.73) — the funding-based ranking has genuine
  cross-sectional signal over random legs, confirming the ranking isn't noise.
- **But loses to cash at every frequency.** 8h rebalance is destroyed by
  turnover (6,102 trades, mean turnover 39% of gross notional per interval →
  total cost drag alone exceeds 700% of capital, textbook "high-frequency
  strategy dies by costs" pattern). Daily rebalance is far better but still
  net negative: gross (no-cost) terminal value would have been **$80,291.89**,
  but 2,032 rebalances at ~45% mean turnover each consumed **276% of capital**
  in round-trip costs, leaving a net **-49.3%** result.
- Decomposition on the daily variant: mean carry_pnl per period (0.025%) is
  smaller than mean price_pnl per period (0.097%) — most of the gross edge is
  directional momentum leaking through the L/S structure (assets with extreme
  funding also tend to have correlated recent price momentum), not a clean
  funding-carry effect. This is consistent with why the effect doesn't survive
  costs: it's a weaker, noisier signal than a pure carry premium would be.
- No cost-robustness variant tested comes close to beating cash, let alone
  the single-asset buy-and-hold benchmarks (equal-weight-10 alone returned
  +855% over the same window). Not worth further parameter tuning — the
  turnover-vs-signal-size ratio is the decisive blocker, not the specific
  tercile/threshold choice.

## Follow-up

Do not retest with alternate lookback/threshold/tercile splits on this same
10-coin universe without a new mechanism — the blocker is structural
(turnover cost dominates the funding carry premium at both tested
frequencies), not a tunable parameter. A slower rebalance (weekly) or a
minimum-holding-period filter could reduce turnover further, but the gross
edge itself (0.025% carry per 8h print) is already small relative to the
30bps round-trip cost, so any rebalance frequency slow enough to survive
costs will likely also dilute most of the carry signal's freshness. Lower
priority than remaining next_hypotheses.md items.
