# Crowded Perpetual Unwind (Funding + Open-Interest Joint Extreme, Short-Only) Validation

Run artifact: `results/crowded_perp_unwind/runs/run-20260901T033917Z/REPORT.md`

## Mechanism (genuinely new in this repo)

- Item #5 from `docs/next_hypotheses.md` — previously blocked ("No; open interest required").
- **New data source, first use in this repo:** real Binance USD-M futures open interest,
  fetched from the public `data.binance.vision` daily-metrics archive
  (`src/crypto_regime_backtest/open_interest_data.py`). No synthetic/proxy OI — missing
  archive days are skipped and reported, never fabricated.
  - Coverage limits (real archive gaps, not a choice): BTCUSDT from 2020-09-01;
    ETHUSDT/SOLUSDT/XRPUSDT from 2021-12-01 only.
- **First short-only directional study in this repo.** Prior funding studies were either
  long-only directional (funding_positive/negative panels), delta-neutral (no price bet),
  or cross-sectional L/S ranking — none combined funding with OI, and none shorted a
  single asset directionally.
- **Primary rule:** short at next hourly open when (a) trailing mean of last 3 completed
  8h funding prints >= +5bps/8h, AND (b) most recent completed daily OI is >= +5% higher
  than 5 days earlier, AND (c) hourly close breaks below the prior-only rolling 24h low
  for the first time since the joint condition became true. Fixed 48h hold, 24h cooldown.
  Funding accrues to the short position while held (a real tailwind, included honestly).
  30bps round-trip cost.

## Result table

| Asset | Trades | Primary final | Buy-and-hold | Daily DCA | Funding-only control | Random control | Top trade % of PnL | Holdout trades |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BTC | 10 | $7,529.35 | $54,646.39 | $16,839.57 | $15,097.02 | $9,718.80 | 77.6% | 0 |
| ETH | 2  | $10,921.42 | $4,081.20 | $8,653.28 | $11,397.58 | $9,678.98 | 86.3% | 0 |
| SOL | 3  | $9,901.41 | $3,553.08 | $14,489.09 | $10,284.07 | $9,833.15 | -614.6% | 0 |
| XRP | 2  | $10,606.87 | $10,662.09 | $15,580.24 | $9,030.30 | $9,802.59 | 148.8% | 0 |

## Honest conclusion

**REJECTED, decisively, on all 4 assets.**

Decisive structural blocker: **zero trades in the 2025-onward test partition on every
asset.** The joint funding+OI+downside-break trigger only fired during the 2021 bull-market
(BTC, 9/10 trades) or scattered 2024 episodes (ETH/SOL/XRP, 2-3 trades each). The joint
condition has not recurred since early 2024 on any of the four majors, so there is no
genuine out-of-sample evidence regardless of in-sample numbers.

Additional independent failures:
- **BTC** loses to cash, buy-and-hold, DCA, the funding-only control, and its own random-
  timing control; fails doubled-cost and best-trade-exclusion; concentration 77.6%
  (single trade dominates).
- **ETH/XRP** beat cash/BH/DCA but fail the concentration cap (86.3% / 148.8% of PnL in
  1-2 trades) — the tiny sample (2 trades each) makes any apparent edge a single-event
  artifact, not a repeatable signal.
- **SOL** loses to cash and DCA; the -614.6% concentration figure reflects a near-zero net
  PnL denominator with an offsetting large single trade, itself a red flag independent of
  sign.
- The funding-only control (no OI, no downside-break confirmation) beat the primary joint
  rule on BTC and ETH — the added OI/breakdown filters did not clearly improve on the
  simpler mechanism, undermining the core economic rationale that OI adds incremental
  information.

No near-miss: unlike the Amihud illiquidity studies, this candidate fails the single most
decisive gate (holdout trades) on every asset, which the skill's own hierarchy treats as
disqualifying regardless of in-sample robustness elsewhere.

## Files

- `results/crowded_perp_unwind/runs/run-20260901T033917Z/REPORT.md`
- `results/crowded_perp_unwind/runs/run-20260901T033917Z/trades.csv`
- `results/crowded_perp_unwind/runs/run-20260901T033917Z/partition_summary.csv`
- `results/crowded_perp_unwind/runs/run-20260901T033917Z/manifest.json`
- `src/crypto_regime_backtest/open_interest_data.py` (new real-OI fetcher, reusable for future OI-based studies)
- `src/crypto_regime_backtest/crowded_perp_unwind_validation.py`
