# SMA(200) Trend-Following with Inverse-Vol Position Sizing — Validation

Run artifact: `results/sma_trend_volscaled/runs/run-20260831T033132Z/`
Script: `scripts/sma_trend_volscaled_validation.py`

## Hypothesis

Preregistered follow-up to the already-**REJECTED** plain binary SMA(200) study
(EXP-2026-08-30-SMA-TREND-001), which failed because a single all-in trade drove
130% of total PnL on every asset. Per this repo's position-sizing-ablation
discipline (current-equity, inverse-vol, capped, no leverage): continuously
scaling exposure by trailing 21-day realized volatility (target 2%/day, weight
capped at 1.0x, current-equity sizing) instead of a binary 0%/100% flag should
reduce concentration while preserving the underlying long-when-trending signal.

- Universe: BTC, ETH, SOL, XRP, real Binance spot 1d OHLCV.
- Signal: long only when `close > SMA200`, weight = `min(1.0, target_vol/realized_vol_21d) * trend_flag`, shifted 1 day (no lookahead).
- Costs: 30bps round-trip on daily turnover.
- Partitions: development (<2020) / validation (2020-2024) / test (2024-2026).
- Falsification (preregistered): must beat B&H on ≥3/4 assets, pass 20% concentration cap and doubled-cost check on every winning asset, and lose the test partition on at most 1 asset.

## Result

| Asset | Vol-scaled final | B&H final | Doubled-cost final | Beats B&H | Concentration (top block) | Test partition |
|---|---:|---:|---:|---|---:|---|
| BTC | 5.65x | 8.54x | 4.58x | No | 0.48 | Lost |
| ETH | 8.07x | 4.04x | 6.76x | **Yes** | 0.45 (fails 0.20 cap) | Won |
| SOL | 3.61x | 5.46x | 3.21x | No | 0.94 | Won |
| XRP | 1.98x | 2.21x | 1.55x | No | 0.93 | Lost |

- Only **1/4 assets (ETH)** beat buy-and-hold — majority gate (≥3/4) fails decisively.
- ETH, the only "winner," **still fails the 20% concentration cap** (0.45) — the fix did not resolve the underlying concentration problem, it just moved where it shows up (fewer, larger vol-scaled blocks instead of one all-in trade).
- BTC/SOL/XRP all trail continuous buy-and-hold outright, worse than or similar to the original binary study's underperformance pattern.
- Doubled-cost check is moot since no asset clears the majority+concentration gates.

## Honest conclusion

**REJECTED.** Inverse-vol continuous position sizing does not rescue the SMA(200) trend-following mechanism on this crypto universe. Unlike the equities/commodities cross-asset SMA200 near-miss (which passed concentration checks), crypto's trend moves remain too large/concentrated relative to the realized-vol scaling window used here — vol-scaling suppressed exposure broadly (mean weight 0.21–0.40, well under 1.0) without preventing a small number of blocks from dominating PnL. Do not retest SMA(200) sizing variants on this universe without a fundamentally different mechanism (e.g., an explicit max-single-trade-PnL cap, or a much wider/adaptive vol window) — expect diminishing returns from further sizing tweaks on this same signal per this program's established concentration-fix compression pattern.

## Files

- `results/sma_trend_volscaled/runs/run-20260831T033132Z/strategy_summary.csv`
- `results/sma_trend_volscaled/runs/run-20260831T033132Z/partition_summary.csv`
- `results/sma_trend_volscaled/runs/run-20260831T033132Z/{BTC,ETH,SOL,XRP}_volscaled_detail.csv`
