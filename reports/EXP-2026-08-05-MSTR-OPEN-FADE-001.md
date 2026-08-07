# EXP-2026-08-05-MSTR-OPEN-FADE-001 — MSTR opening fade after BTC overnight sell-offs

**Verdict: REJECTED FOR DEPLOYMENT.** None of the predeclared 5-, 10-, or
15-minute exits had a positive average net return in the development window, so
there is no rule to carry into validation or paper trading.

## Frozen hypothesis

On a US equity session, use only the BTCUSDT return from the prior US equity
close through the completed 09:25 ET five-minute bar. Flag it when its absolute
return exceeds the expanding, prior-data-only 95th percentile after 60 prior
sessions. When the flagged BTC return is negative, buy MSTR at the 09:30 ET
opening print and sell at the close of the 09:34, 09:39, or 09:44 bar. Deduct
20 bps per executed round trip.

The three exits were a declared development-only choice set. Selection would
have been the highest positive 2021--2023 mean net return. The study uses the
licensed Nasdaq one-minute OHLCV cache and Binance BTCUSDT five-minute cache.
It has no bid/ask data: the cost model is a conservative proxy, not proof of
opening-auction fill quality.

## Result

| Period | Events | 5 min | 10 min | 15 min |
|---|---:|---:|---:|---:|
| Development: 2021--2023 | 7 | -0.506% mean; -4.08% compounded | -1.389% mean; -9.92% compounded | -0.581% mean; -4.61% compounded |
| Locked validation: 2024 | 3 | +1.536%; +4.54% | +3.560%; +10.73% | +3.049%; +9.08% |
| Observed later period: 2025--Aug 2026 | 5 | +1.102%; +5.55% | +1.318%; +6.59% | +1.032%; +5.11% |
| Full observed sample | 15 | +0.438%; +5.84% | +0.503%; +6.32% | +0.683%; +9.38% |

The apparently positive later periods do not rescue the strategy: they were not
available when the selection decision was made, have just 3 and 5 events, and
all 95% bootstrap intervals include zero. Selecting a horizon after seeing
them would be look-ahead selection.

## Decision

Do not use this as a live or paper trading rule, and do not create a
TradingView/capital-deployment handoff. The result falsifies the specific
"buy MSTR at open after BTC tanks, sell 5/10/15 minutes later" claim under the
predeclared event definition. A materially different signal would be a new
hypothesis, requiring a new preregistration and untouched observation period.

## Reproduce

```bash
.venv/bin/edge-research mstr-open-fade
```

The machine-readable result, including every event-level net return, is in
[`EXP-2026-08-05-MSTR-OPEN-FADE-001_summary.json`](EXP-2026-08-05-MSTR-OPEN-FADE-001_summary.json).
