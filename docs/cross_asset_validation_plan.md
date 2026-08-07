# Crypto-equity event validation plan

**Frozen experiment:** `EXP-2026-08-04-CROSS-ASSET-001`  
**Scope:** requested ideas 6, 7, and 8  
**Status:** studies 6 and 7 completed; study 8 provider acquisition incomplete

## Decision questions

1. After a wild crypto weekend or overnight move, do crypto-linked equities exhibit a tradable opening gap, continuation, or reversal after realistic entry timing and costs?
2. Does BTC lead crypto equities in a way that predicts the residual return after the US open, rather than merely describing their shared exposure?
3. Do liquidation size and direction add out-of-sample information after controlling for the BTC move, BTC volatility, and US equity factors?

## Universe and point-in-time controls

The primary cohort contains the 20 direct-exposure names frozen in `configs/cross_asset_events.yaml`, plus SPY and QQQ controls. A ticker is eligible only after its first Databento definition and before its final definition. Symbol mappings, listing dates, renames such as SQ to XYZ, and delistings must be resolved from Databento definitions. Current ETF holdings may help discover candidates but must never be treated as historical membership.

Results are first reported by predeclared cohorts (treasury companies, exchanges/brokers, miners/infrastructure, and payments), then by ticker. No ticker is allowed to contribute more than 25% of claimed strategy profit.

## Events and execution

- Weekend BTC return: Friday 16:00 ET to Monday 09:25 ET.
- Overnight BTC return: prior US equity close to 09:25 ET.
- Primary wild event: absolute return exceeds its expanding prior-sample 95th percentile after at least 60 prior observations.
- Sensitivity only: expanding 90th percentile. This is not an alternate threshold to select after seeing P&L.
- Tradable entry: 09:35–09:40 ET VWAP. The opening print and 09:25 BTC price are signals, not assumed fills.
- Outcomes: opening gap, entry-to-close, next session, and three sessions.

For each equity, its expected opening response is estimated from the prior 60 sessions of BTC sensitivity, with at least 40 observations, then adjusted for SPY/QQQ. The core signal is the residual opening gap: observed gap minus the response expected from BTC and equity factors. Continuation and reversal are tested separately and never combined after the fact.

## Liquidation increment test

CoinGlass aggregate BTC long and short liquidations are rolled over 24 hours. Events are identified by either the frozen $800 million level or the expanding prior-sample 99th percentile, and classified as long cascades, short squeezes, or two-sided churn.

The required comparison is:

`equity return ~ BTC return + BTC volatility + SPY/QQQ factors`

versus:

`equity return ~ BTC return + BTC volatility + SPY/QQQ factors + liquidation size + liquidation imbalance`

Study 8 is rejected if the liquidation terms do not improve untouched out-of-sample performance after costs. A Hyperliquid-only fallback must be labelled venue-specific and cannot support a claim about aggregate market liquidations.

## Robustness and rejection rules

- Block bootstrap by event date; never treat stocks hit by the same event as independent observations.
- Benjamini–Hochberg correction across event definitions, horizons, cohorts, and directions.
- Leave-one-event-out and leave-one-ticker-out stability.
- Reject if one event or ticker supplies more than 25% of total claimed P&L.
- Include entry/exit slippage, spread sensitivity, commissions, and borrow constraints for short results.
- Keep development, validation, and final windows separate as configured; do not use the final window for threshold selection.
- Report event count, coverage gaps, survivorship limitations, and a null result as first-class evidence.

## Current data gate

Databento job `XNAS-20260804-ED35KSK6WW` delivered 7,482,129 one-minute XNAS.ITCH records at an approved cost of $4.682681. Studies 6 and 7 are reported in `reports/EXP-2026-08-04-CROSS-ASSET-001.md`. CoinGlass authentication works, but the supplied plan returns `Upgrade plan` for aggregate liquidation history, so the cross-exchange version of study 8 still awaits CoinGlass entitlement.
