# BTC-to-crypto-equity opening-gap strategy

**Experiment:** `EXP-2026-08-05-CROSS-ASSET-STRAT-001`  
**Parent evidence:** `EXP-2026-08-04-CROSS-ASSET-001`  
**Status:** completed; formal strategy rejected for deployment

## Economic premise

BTC trades continuously while US crypto-related equities are closed. Studies 6 and 7 found that BTC strongly predicts the direction and size of the crypto-equity opening gap, but did not establish a reliable post-09:35 edge in the shorter sample. This strategy test asks the narrower executable question: after an unusually large BTC move, does the portion of the equity gap unexplained by lagged sensitivities continue or reverse between 09:35 and the close?

## Timeline

1. At the prior US equity close, record BTC and the equity closes.
2. At 09:25 ET, use the last completed five-minute BTC candle. No later BTC or equity information is permitted in the event signal.
3. Classify a wild event when the absolute BTC return exceeds the expanding prior-sample 95th percentile after 60 observations.
4. Estimate each equity's BTC, SPY, and QQQ sensitivities from the previous 60 sessions, requiring 40 complete observations.
5. Compare the observed 09:35–09:39 equity gap with its expected factor response.
6. Only after that observation window is complete, enter an equal-weight portfolio during 09:40–09:44 and exit during 15:55–15:59.

## Frozen candidate rules

- `btc_continuation`: trade in the direction of the overnight BTC move.
- `btc_reversal`: trade against the overnight BTC move.
- `residual_continuation`: trade in the direction of the unexplained opening gap.
- `residual_reversion`: trade against the unexplained opening gap.

Only 5 August 2021 through 31 December 2023 may select the rule. The candidate with the highest positive mean net event return is locked; if every candidate is negative, the system selects no strategy. The locked rule is then evaluated without changes in calendar 2024 and in the untouched 2025–3 August 2026 forward window.

## Portfolio and costs

- Equal capital allocation across eligible non-benchmark equities on each event.
- Primary cost: 20 bps round trip per entered stock.
- Stress cost: 50 bps round trip.
- Starting research capital: $10,000.
- Cash earns zero between events.
- Primary results allow intraday long and short positions; a long-only sensitivity is reported because borrow availability is not modeled.
- A liquid-session sensitivity requires at least 300 observed one-minute bars for each included stock that day.

## Acceptance requirements

The locked rule must have positive total return in both validation and forward windows, a forward event-return bootstrap lower bound above zero, positive forward returns under the liquid-session and 50 bps cost tests, and no single event contributing more than 25% of forward gross profits. Failure of any requirement prevents promotion beyond historical research.
