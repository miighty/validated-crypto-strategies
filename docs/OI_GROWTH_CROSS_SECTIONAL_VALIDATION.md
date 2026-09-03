# EXP-2026-09-03-OIXSMOM-001: Cross-sectional Open-Interest Growth Ranking

## Hypothesis (preregistered)
Real Binance USD-M futures open interest, ranked **cross-sectionally**
(long top-tercile 7-day OI growth / short bottom-tercile), identifies assets
attracting fresh leveraged demand vs assets seeing leverage unwind, earning a
premium net of costs. Distinct from every prior single-asset OI study in this
repo (event trigger: `CROWDED_PERP_UNWIND`, `OI_BREAKOUT_CONFIRMATION`,
`OI_THIN_BREAKOUT`; slow SMA-crossover regime: `OI_TREND_REGIME`), all four of
which were REJECTED. Also distinct from the four prior dollar-neutral
cross-sectional factor rejections (Amihud, funding-carry, residual-momentum,
low-vol) which used a different underlying data field.

## Data
- Real Binance USD-M futures OI archive (`data/open_interest/*_oi_daily.csv.gz`),
  10-coin universe limited by real archive coverage: BTC, ETH, SOL, XRP, BNB,
  ADA, DOGE, AVAX, LINK, ATOM (2021-12-01 through 2026-08-30/09-02).
- Real Binance spot daily OHLCV (`data/raw/*_1d.csv.gz`) for price returns.
- No proxy/synthetic data used anywhere.

## Design
- OI growth score: `oi_t / oi_{t-7} - 1`, shifted 1 day (no same-day lookahead).
- Weekly rebalance, long top tercile / short bottom tercile, equal-weighted,
  dollar-neutral (50%/50% gross), 30bps round-trip cost, same mechanics as
  `amihud_illiquidity_cross_sectional.py`.
- Controls: seeded random-ranking L/S (same leg sizes/turnover/cost).
- Benchmarks: cash, equal-weight-10 BH, BTC/ETH/SOL/XRP BH.
- First-pass robustness gates (per skill's delay-robustness discipline): 1-bar
  execution delay, doubled cost, cross-sectional label-scramble Monte Carlo
  (n=500, proper null for a ranking strategy).

## Result
| Strategy | Final capital | Sharpe | Top-trade % PnL |
|---|---:|---:|---:|
| OI-growth L/S (primary) | $7,045 | -0.29 | 45.2% |
| OI-growth L/S, 1-bar delay | $4,885 | -0.81 | 14.5% |
| OI-growth L/S, 2x cost | $4,092 | -0.88 | 16.4% |
| Random-ranking L/S control | $2,993 | -1.06 | 19.8% |
| Equal-weight-10 BH | $4,700 | 0.07 | n/a |
| BTC BH | $11,149 | 0.30 | n/a |
| Cash | $10,000 | n/a | n/a |

Cross-sectional label-scramble MC (n=500): observed $7,045 vs sim mean
$5,971 ± $2,816 → **p=0.2660 (not significant)**.

## Gates
- Beats random control: **True** (weak positive, both legs deeply negative)
- Beats cash: **False** — loses 29.5% of capital outright
- Concentration ≤20%: **False** (45.2%)
- 1-bar delay retains ≥50% of Sharpe: **False** (Sharpe flips more negative)
- MC significant (p≤0.05): **False** (p=0.27)

## Verdict: REJECTED (decisive)
Every preregistered gate fails except beating the random control, and even
that is beating a control that also lost money — both the strategy and its
control lost real capital, meaning the "edge" over random is really just
noise around a shared loss, not a genuine signal. Loses outright to cash and
to buy-and-hold on this 10-coin universe.

## Notes for future work
- Twelfth OI-related study in this program (5th cross-sectional-style
  construction after Amihud/funding-carry/residual-momentum/low-vol) — closes
  out the OI data source for cross-sectional ranking on this small 10-coin
  universe. The narrower coverage (10 vs the 30-coin spot universe) may be
  contributing, but the strategy loses to cash outright regardless of
  universe-size caveats, so this is not a near-miss worth universe expansion
  without new OI archive coverage for more assets.
- Do not retest 7-day OI growth ranking on this exact universe without new
  data (broader OI archive coverage) or a different growth window.
- Items 1-3 in `docs/next_hypotheses.md` remain the highest-priority untested
  single-asset/single-mechanism ideas.
