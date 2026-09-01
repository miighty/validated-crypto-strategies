# Open-Interest Trend (SMA20/SMA60 Crossover) Regime Filter Validation

Run artifact: `results/oi_trend_regime/runs/run-20260901T161052Z/REPORT.md`

## Hypothesis

Sustained expansion of aggregate leveraged positioning (a fast rolling mean
of open interest trending above a slower rolling mean) reflects durable,
broadening participation and should precede stronger price action; the
inverse crossover should precede weaker price action. Structural regime
filter, distinct from every prior OI use in this repo (which used OI as a
discrete short-window %-change confirmation/crowding trigger, not a
continuous SMA-crossover state).

## Primary rule

- Per-asset (BTC/ETH/SOL/XRP independently): long while rolling 20-day mean
  of real Binance USD-M daily open interest > rolling 60-day mean; flat
  otherwise. Regime flag known as of day t, executed at the next daily bar's
  open. 30bps round-trip cost.
- OI coverage: real archive limits (BTC from 2020-09-01, ETH/SOL/XRP from
  2021-12-01), no fabrication.

## Result table

| Asset | Primary | Buy-and-hold | DCA | Momentum control | Random control | Top-block %PnL | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| BTC | 0.51x | 5.61x | 1.73x | 11.34x | 1.48x | 71.0% | REJECTED |
| ETH | 1.28x | 0.42x | 0.89x | 2.60x | 0.30x | 380.1% | REJECTED |
| SOL | 1.58x | 0.37x | 1.50x | 1.27x | 0.10x | 144.6% | REJECTED |
| XRP | 1.65x | 1.11x | 1.62x | 1.97x | 0.50x | 272.6% | REJECTED |

## Honest conclusion

**REJECTED, decisively, on all 4 assets.**

- BTC loses outright: the regime filter finishes below its own starting
  capital (0.51x) and loses to buy-and-hold, DCA, the momentum control, and
  the random-regime control simultaneously.
- ETH/SOL/XRP beat buy-and-hold and the random-regime control, but all four
  assets fail the concentration cap badly (top single block = 71%-380% of
  total strategy PnL) -- the same concentration-artifact failure mode
  already documented for SMA-200, DVOL-fear-spike, and stablecoin-supply
  trend in this program. 3/4 assets (BTC/ETH/XRP) also lose to the naive
  BTC-price-momentum regime control, undermining the claim that OI trend
  adds information beyond simple price momentum.
- 3/4 assets (BTC/ETH/XRP) fail the best-block-exclusion check outright.

## Decisive blockers

1. Concentration cap violated on all 4 assets (71%-380%, vs the 20% cap).
2. 3/4 assets lose to the simpler BTC-momentum regime control -- OI trend
   does not add value over plain price momentum.
3. BTC additionally loses outright to buy-and-hold/DCA/momentum/random.

## Files

- `results/oi_trend_regime/runs/run-20260901T161052Z/REPORT.md`
- `results/oi_trend_regime/runs/run-20260901T161052Z/{BTC,ETH,SOL,XRP}_trades.csv`
- `results/oi_trend_regime/runs/run-20260901T161052Z/{BTC,ETH,SOL,XRP}_gates.json`
