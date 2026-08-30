# Small/Mid-Cap Amihud Illiquidity — Bybit Cross-Exchange Replication

**Experiment ID:** EXP-2026-08-30-AMIHUD-SMALLCAP-BYBIT-001
**Date:** 2026-08-30
**Status:** COMPLETED — cross-exchange replication of the "promising but inconclusive" EXP-2026-08-30-AMIHUD-SMALLCAP-001

## Hypothesis
The small/mid-cap Amihud illiquidity premium (long most-illiquid tercile / short most-liquid
tercile, real Binance data, 54-coin universe ranked ~100-400 by market cap) previously scored
Sharpe 1.43, passed MC/walk-forward/cost-robustness, but failed Deflated Sharpe (p=0.121).
Per the skill's near-miss discipline, the prescribed next step is cross-exchange replication
before any capital-allocation decision. This tests the **identical mechanism/parameters** on
**independently-sourced Bybit spot OHLCV**.

## Universe
- 42 of the original 54 coins are listed on Bybit spot USDT markets (12 missing, not
  substituted: CFX, CVX, DCR, GLM, GNO, IOTA, NEO, PROM, RAY, SFP, SYRUP, XEC).
- Real history per coin: 593–1,803 daily rows (fetched fresh via ccxt, 2026-08-30).
- Analysis window: 2021-09-23 → 2026-08-30 (bounded by shortest-history coin after the
  14-day illiquidity lookback + tercile-ranking minimum-9-names requirement).

## Method
Identical to EXP-2026-08-30-AMIHUD-SMALLCAP-001: 14-day rolling Amihud ratio (shift 1, no
lookahead), 7-day rebalance, long/short tercile, 50/50 dollar-neutral, 30bps round-trip cost.

## Results

| Check | Sharpe | Final capital | Total return | Concentration |
| --- | --- | --- | --- | --- |
| Baseline (30bps) | **1.51** | $46,102.77 | +261.03% | 9.3% (well under 20% cap) |
| Random-ranking control | 0.57 | $16,567.28 | +65.67% | — |
| Doubled cost (60bps) | 1.51 (unchanged) | $42,414.87 | +224.15% | 9.6% |
| 1-day execution delay | 1.57 (improves) | $51,801.20 | +318.01% | 8.1% |
| First half (2021-09→2024-03) | 1.53 | — | +149.68% | 15.7% |
| Second half (2024-03→2026-08) | 1.61 | — | +82.41% | 16.1% |

- Cross-sectional label-scramble Monte Carlo (n_trials=500): **p=0.0000** (decisive, both final-capital and Sharpe statistics)
- Deflated Sharpe (n_trials=90, program's true search size incl. this study): **p=0.218 — fails significance**
- Block-bootstrap 95% CI on mean trade return: [0.00244, 0.01125] — excludes zero
- Best-trade exclusion: total PnL $36,102.77 → $32,747.69 excluding the single best trade, still strongly profitable

## Interpretation — CONFIRMS the original result, does not merely partially replicate it
Unlike the top-30 Amihud cross-exchange check (Binance 1.73 → Bybit 0.57-0.74, roughly
half the magnitude), **this small/mid-cap variant showed NO magnitude decay across venues**:
Binance Sharpe 1.43 → Bybit Sharpe 1.51 (essentially the same, on a 42/54-coin overlapping
subset). Walk-forward shows no decay on Bybit either (1.53 → 1.61, second half improving),
mirroring the original Binance finding (1.47 → 1.62).

The strategy clears every bar this program tests **except Deflated Sharpe**, on a second,
independently-sourced exchange. This is now the strongest and most consistently-replicated
cross-sectional factor result in this repo's research program.

## Verdict: PROMISING BUT INCONCLUSIVE (confirmed on cross-exchange replication)
Same verdict class as the original Binance study — passes MC significance, walk-forward,
cost/delay robustness, and concentration cap on BOTH Binance and Bybit; fails Deflated Sharpe
on both (Binance p=0.121, Bybit p=0.218) at the program's multiple-testing scale. Per the
skill's own MC-vs-DSR distinction: MC says the ranking signal is real and reproducible across
two independent venues; DSR says it doesn't clear the bar for capital allocation given how many
strategy variants this program has searched. Both statements are true and not contradictory.

## Next step if revisited
- OKX cross-check for a third independent venue (per skill's cross-exchange note pattern),
  OR
- Accept this as a durable "no-deploy, high-confidence-signal-is-real" research finding and
  deprioritize further validation compute on this exact factor — the marginal information from
  a third exchange is unlikely to change the DSR conclusion given the program's growing search
  count (each new check itself adds to `n_trials`).
