# Crypto equities after wild BTC moves: studies 6 and 7

**Experiment:** `EXP-2026-08-04-CROSS-ASSET-001`  
**Verdict 6:** **REACTION CONFIRMED; TRADABLE EDGE REJECTED**  
**Verdict 7:** **BTC LEAD CONFIRMED; ORIGINAL P&L TEST WITHDRAWN**  
**Study 8:** deliberately not run in this report

> **Execution correction (5 August 2026):** The descriptive BTC-to-opening-gap results remain valid. The residual continuation/reversion P&L table below used the same 09:35–09:39 window to observe the gap and proxy the fill, which is not executable without lookahead. Those residual-strategy P&L figures are withdrawn. The corrected strategy validation observes 09:35–09:39 and enters 09:40–09:44; see `EXP-2026-08-05-CROSS-ASSET-STRAT-001.md`.

## Executive result

BTC moves strongly explain how the focused crypto-equity cohort opens. Across 607 eligible sessions, BTC's prior-close-to-09:25 return had a **0.736 correlation** with the cohort's 09:35–09:40 opening gap; the relationship rose to **0.932** on the 25 expanding-95th-percentile wild sessions. The gap matched BTC's direction on **77.8%** of all sessions and **100%** of wild sessions.

That is evidence that BTC leads the US opening repricing. The original same-window residual P&L test is not valid execution evidence and is superseded by the corrected 09:40-entry five-year strategy report. That later test found a historically profitable alternative but still rejected it for deployment.

## Study 6 — wild nights and weekends

### Wild overnight moves

The primary threshold is the expanding prior-sample 95th percentile of absolute BTC overnight returns after 60 prior observations. Returns below are equal-weight cohort means by event date; the 95% intervals resample event dates rather than treating stocks hit by the same BTC move as independent.

| BTC event | Events | Opening gap | 95% interval | 09:35–close | 95% interval | Entry–next close | 95% interval |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Wild BTC up | 12 | +5.61% | +4.25% to +7.21% | +0.48% | -2.13% to +2.73% | +0.06% | -2.97% to +2.98% |
| Wild BTC down | 13 | -5.49% | -7.23% to -4.05% | +1.33% | -1.80% to +4.38% | +1.98% | -1.18% to +5.21% |
| All wild events | 25 | -0.16% | -2.69% to +2.20% | +0.92% | -1.19% to +2.91% | +1.06% | -1.11% to +3.42% |

The opening response is large, directional, and statistically clear. Every post-entry interval includes zero. This supports **repricing before the tradable entry**, not a dependable continuation or rebound trade afterward.

The expanding 90th-percentile sensitivity produced 46 events and the same result: up events opened +4.61%, down events -4.48%, while post-entry intervals still crossed zero.

### Wild weekends

The weekend distribution has only one eligible primary event after the required 60-weekend warm-up. The 90th-percentile sensitivity has four events. That is insufficient for inference, and the seemingly negative next-session result from four observations is not accepted as an edge. The weekend-specific hypothesis remains **underpowered**, not validated.

## Study 7 — does BTC lead or lag crypto equities?

Each stock's expected gap was estimated from the prior 60 sessions of BTC, SPY, and QQQ sensitivity, requiring at least 40 observations. The observed gap minus that expected response formed the residual. Two opposing rules were tested: trade with the residual (continuation) or against it (reversion).

| Sample and rule | Sessions | Mean net return | Win rate | Event-date bootstrap 95% interval | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| All sessions — residual reversion | 607 | +0.10% | 51.9% | -0.18% to +0.36% | Reject |
| All sessions — residual continuation | 607 | -0.50% | 43.7% | -0.76% to -0.22% | Reject |
| Wild sessions — residual reversion | 25 | -0.84% | 44.0% | -3.13% to +1.38% | Reject |
| Wild sessions — residual continuation | 25 | +0.44% | 52.0% | -1.78% to +2.73% | Reject |

In the stricter sample requiring at least 300 observed trading minutes per stock-session, all-session reversion fell to +0.03% with a -0.25% to +0.30% interval. Wild-session continuation fell to +0.10% with a -2.10% to +2.38% interval. The apparent positives are therefore not stable enough to claim.

## Data and execution

- **Equities:** Databento `XNAS.ITCH`, one-minute OHLCV, 1 January 2024 through 3 August 2026; job `XNAS-20260804-ED35KSK6WW`.
- **Equity records:** 7,482,129 source bars; 13,565 usable symbol-sessions across 22 symbols including SPY and QQQ controls.
- **BTC:** Binance spot BTCUSDT, 272,448 five-minute bars with no missing candles.
- **Signal cutoff:** last completed BTC candle at 09:25 ET.
- **Entry:** volume-weighted typical-price proxy from the 09:35–09:39 one-minute OHLCV bars.
- **Exit:** equivalent proxy from 15:55–15:59.
- **Costs:** 10 bps entry slippage plus 10 bps exit slippage; no commission.
- **Corporate actions:** mechanical split adjustment detected one MSTR and one IBKR split; the unadjusted split discontinuities were removed before returns were calculated.
- **Data cost:** $4.682681 from Databento, matching the approved $4.68 preflight estimate.

The focused cohort was MSTR, COIN, MARA, RIOT, CLSK, HUT, HIVE, IREN, WULF, CORZ, CIFR, BTDR, APLD, HOOD, PYPL, XYZ, IBKR, CAN, BTBT, and GLXY. GLXY begins with its US listing in May 2025; XYZ begins under that ticker in January 2025. Unavailable history was not fabricated.

## Limitations

- XNAS.ITCH is Nasdaq venue data rather than a consolidated all-venue feed. Thin names have fewer observed trading minutes, which is why the 300-minute sensitivity is reported.
- The OHLCV entry is a volume-weighted typical-price proxy, not trade-by-trade VWAP.
- The 2024–2026 period contains too few post-warm-up wild weekends for a weekend conclusion.
- This is a focused direct-exposure cohort, not yet the exhaustive point-in-time universe of every listed crypto-related equity.
- Borrow availability and borrow fees are not included; negative/short interpretations therefore face an additional real-world constraint.

## Decision

Do not promote the original same-window residual test to TradingView or execution. BTC remains a strong descriptive leader of the opening gap. The corrected later-entry five-year strategy is documented separately and is also not approved for deployment.
