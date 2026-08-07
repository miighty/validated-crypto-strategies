# Forward-only paper test: operating procedure

## Evidence boundary

The earlier 2025–3 August 2026 segment was chronological, but it was no longer pristine
after its results had been viewed during strategy development. The independent observation
clock therefore restarts on **5 August 2026**, with the strategy frozen before that day's
09:25 America/New_York signal.

This is a finalized-data paper observer. It submits no orders and reads no broker credentials.
Running it after the close is intentional: the 09:25 signal, 09:35–09:39 observation,
09:40–09:44 assumed entry and 15:55–15:59 assumed exit are reconstructed mechanically from
the finalized bars under a rule that was locked before the session occurred.

## Daily operation

1. After 16:05 America/New_York, download that session's Databento XNAS.ITCH `ohlcv-1m`
   files for the frozen universe into the licensed local cache. Then rebuild the combined panel:

   ```bash
   .venv/bin/edge-research cross-asset-forward-prepare \
     --forward-roots data/cache/cross_asset/forward/databento
   ```

   This combines the new files with the original five-year panel and adjusts corporate actions
   once across the full sequence.
2. Refresh the public Binance BTCUSDT five-minute file through at least the session's 15:55
   New York candle:

   ```bash
   .venv/bin/edge-research download --config configs/cross_asset_btc_forward.yaml
   ```
3. Append all finalized sessions through the date:

   ```bash
   .venv/bin/edge-research cross-asset-forward --through YYYY-MM-DD
   ```

4. Inspect `forward/cross_asset_paper_status.json`. A normal day is recorded even when no
   wild event occurs. Re-running the same date appends nothing. Editing an earlier ledger row
   breaks the hash-chain verification and stops the next run.

The input panel is deliberately not downloaded implicitly by the observation command. This
prevents an accidental Databento charge and keeps licensed raw data out of Git. The ledger
stores derived observations only.

## Frozen promotion review

Review is disabled until at least 30 entirely new wild-event sessions exist. At that point,
all of the following must hold: positive primary compounded return, positive 50 bps cost
stress return, positive liquid-session return, a positive lower bound for the bootstrapped
mean event return, and no event contributing more than 25% of positive event returns.

Passing the gates changes the status only to `ready_for_independent_review`. The system always
reports `live_trading_approved: false`; capital deployment requires a separate decision.

## TradingView companion

`pine/btc_crypto_equity_residual_continuation.pine` is a supplementary per-stock Pine v6
replication. Apply it to a standard one-minute chart for one frozen-universe equity at a time
with Extended Trading Hours enabled. Its default window is the independent 5 August 2026
forward start, its order size is one 5% portfolio slot, and its 0.10% commission per side
represents the frozen 20 bps round trip.

TradingView cannot aggregate the 20 separately charted equities into the authoritative
equal-slot portfolio. Feed alignment, bar-based fills and TradingView's vendor data can also
differ from the Databento typical-price proxies. Consequently, Pine is for visual review and
per-stock paper diagnostics; the hash-chained Python ledger remains the promotion authority.

The first TradingView check on 5 August 2026 compiled and ran without a Pine error on MSTR,
one-minute bars and Extended Trading Hours. The Basic account exposed only 27 July onward at
that resolution, which is shorter than the frozen 60-session warm-up, and the clean forward
session had not closed. The correct Strategy Tester result is therefore **awaiting data**, not
zero return. The test record is `reports/tradingview/EXP-2026-08-05-CROSS-ASSET-FORWARD-001.json`.
