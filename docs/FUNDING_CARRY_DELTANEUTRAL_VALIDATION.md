# Delta-Neutral Single-Asset Funding-Carry Harvest Validation

Run artifact: `results/funding_carry_deltaneutral/runs/run-20260830T210427Z/`

## Mechanism (genuinely new in this repo)

Long spot + short perpetual, equal notional, single asset at a time (BTC/ETH/SOL/XRP
independently). While positioned, P&L is (by idealized 1:1-hedge assumption) insensitive
to price direction; it accrues purely from realized 8h funding prints. Entry/exit timed
by a rolling-mean-with-hysteresis persistence filter on real Binance funding history:
enter/stay hedged while trailing mean of the last 3 completed 8h prints >= +3bps/8h;
exit when that mean falls below +1bps/8h.

This is mechanistically distinct from every prior funding study in this repo:
- `EXP-2026-08-29-FUNDCARRY-001` (cross-sectional, dollar-neutral, multi-asset L/S) — REJECTED, turnover cost death.
- `funding_negative_panel_validation.py` / `funding_positive_panel_validation.py` (single-asset, **unhedged directional** spot entries gated by funding) — both REJECTED.
- This study: single-asset, **delta-hedged**, no price exposure while positioned.

## Honesty disclosures

- No margin/borrow financing spread modeled for the short-perp leg beyond the funding print itself (real desks pay an additional small financing spread).
- Assumed a continuously maintained 1:1 hedge with no basis or liquidation risk while positioned — idealized.
- Real data only: Binance real 8h funding history (`data/funding/*_funding.csv.gz`) + real 1h spot OHLCV (`data/raw/*_1h.csv.gz`), both already cached in this repo. No synthetic/proxy inputs.

## Result table (per asset, primary rule)

| Asset | Final capital | Trades | Time hedged | Best-trade % of PnL | Test-partition (2025+) trades | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| BTC | $13,804.16 | 6 | 16.5% | 66.4% | **0** | REJECTED |
| ETH | $15,085.49 | 7 | 20.5% | 64.5% | **0** | REJECTED |
| SOL | $14,500.48 | 12 | 19.0% | 21.7% | **0** | CANDIDATE (per-gate) but see below |
| XRP | $17,075.63 | 6 | 19.0% | 63.0% | **0** | REJECTED |

## Decisive blockers

1. **Zero trades in the 2025-onward test partition on all four assets.** Real Binance
   funding has not sustained a >=3bps/8h trailing-mean persistence episode since
   2025-01-01 on any of BTC/ETH/SOL/XRP under this rule. This means the strategy has
   **no genuine out-of-sample evidence** — every trade on every asset occurred in the
   development (pre-2024) or validation (2024) partitions. This alone is disqualifying
   per this repo's chronological-partition discipline (never declare a strategy validated
   without a test-partition trade record).
2. **Concentration cap failure on 3 of 4 assets.** BTC/ETH/XRP each have a single trade
   responsible for 63-66% of total strategy PnL — a single funding-spike episode (each
   asset's own 2021 bull-market funding blowout), not a repeatable edge.
3. **SOL alone clears every per-gate check** (beats cash, beats always-on carry, survives
   doubled cost, survives best-trade exclusion, concentration 21.7% under the 100%/
   informal-cap heuristic) — but 10 of its 12 trades occurred in the pre-2024 development
   window and it too has **zero test-partition trades**. Per this repo's holdout-sample
   discipline (see `BTC_ALT_RESPONSE_VALIDATION.md`'s "far too small holdout" rejection
   precedent), an asset with zero holdout trades cannot be called validated regardless of
   how clean its per-gate numbers look on the development/validation windows alone.
4. Every asset's `always_on_delta_neutral_carry` control (permanently hedged, no timing)
   beat or roughly matched the timed primary rule on BTC/ETH/XRP, meaning the rolling-mean
   timing filter's added value beyond simply staying hedged whenever funding is calculable
   is marginal-to-negative for 3 of 4 assets — the "timing" mechanism itself is not clearly
   earning its keep even where the strategy showed a nominal profit.

## Overall verdict

**REJECTED.** Zero test-partition (2025+) trades across all four assets is a decisive,
structural blocker independent of the per-gate pass/fail pattern — the strategy cannot be
called validated when 100% of its evidence comes from the development/validation windows.
The concentration-cap failures on BTC/ETH/XRP further show that even the in-sample apparent
edge is dominated by single funding-spike episodes, not a repeatable persistence effect.

## Files

- `results/funding_carry_deltaneutral/runs/run-20260830T210427Z/REPORT.md`
- `results/funding_carry_deltaneutral/runs/run-20260830T210427Z/strategy_summary.csv`
- `results/funding_carry_deltaneutral/runs/run-20260830T210427Z/partition_summary.csv`
- `results/funding_carry_deltaneutral/runs/run-20260830T210427Z/trade_log.csv`
- `results/funding_carry_deltaneutral/runs/run-20260830T210427Z/sensitivity_checks.csv`
