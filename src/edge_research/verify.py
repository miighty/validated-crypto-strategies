from __future__ import annotations

import json
from pathlib import Path

from .config import load_yaml, project_root
from .data import load_market_data

EXPERIMENT_CONFIGS = (
    "configs/rsi_mean_reversion.yaml",
    "configs/breakout_acceptance.yaml",
)
TRADINGVIEW_SYMBOLS = {"BINANCE:BTCUSDT", "BINANCE:ETHUSDT", "BINANCE:SOLUSDT"}


def verify_pine_contract(path: Path, experiment_type: str) -> None:
    source = path.read_text()
    required = (
        "//@version=6",
        "strategy(",
        "pyramiding = 0",
        "process_orders_on_close = false",
        "barstate.isconfirmed",
        '"Development 2016–2020"',
        '"Validation 2020–2024"',
        '"Forward 2024–2026"',
    )
    missing = [token for token in required if token not in source]
    if missing:
        raise ValueError(f"{path}: missing Pine contract tokens: {missing}")
    if "calc_on_order_fills" in source:
        raise ValueError(f"{path}: calc_on_order_fills is forbidden by the replication contract")
    if experiment_type == "rsi_mean_reversion" and "ta.rsi(close, rsiPeriod)" not in source:
        raise ValueError(f"{path}: RSI implementation is missing")
    if experiment_type == "breakout_acceptance_rejection":
        breakout_required = (
            "ta.highest(high[1]",
            'input.string("Immediate Long", "Variant"',
            'input.int(50, "Previous-high lookback"',
            'input.int(2, "Acceptance/rejection window"',
            'input.float(0.1, "Level buffer (ATR)"',
        )
        missing_breakout = [token for token in breakout_required if token not in source]
        if missing_breakout:
            raise ValueError(f"{path}: selected breakout contract is missing: {missing_breakout}")


def verify_cross_asset_pine_contract(path: Path) -> None:
    source = path.read_text()
    required = (
        "//@version=6",
        "strategy(",
        "default_qty_value = 5",
        "commission_value = 0.10",
        "pyramiding = 0",
        "calc_on_order_fills = false",
        "calc_on_every_tick = false",
        "process_orders_on_close = false",
        '"Forward only — from 2026-08-05"',
        'input.symbol("BINANCE:BTCUSDT"',
        '"AMEX:SPY"',
        '"NASDAQ:QQQ"',
        "array.percentile_linear_interpolation(ordered, 95)",
        "observations >= 40",
        "f_push_capped(responseHistory, stockReturn, 60)",
        "if at0925 and not na(priorBtcClose)",
        "if at0940",
        "if at1558",
        'strategy.entry("Residual continuation long", strategy.long',
        'strategy.close("Residual continuation long"',
    )
    missing = [token for token in required if token not in source]
    if missing:
        raise ValueError(f"{path}: missing cross-asset Pine contract tokens: {missing}")
    forbidden = ("strategy.short", "lookahead = barmerge.lookahead_on)\n[spyTypical")
    present = [token for token in forbidden if token in source]
    if present:
        raise ValueError(f"{path}: forbidden cross-asset Pine tokens: {present}")


def verify_tradingview_record(path: Path) -> str:
    record = json.loads(path.read_text())
    expected_status = "SUPPLEMENTARY_FORWARD_TESTED_HISTORICAL_WINDOWS_DEFERRED"
    if record.get("status") != expected_status:
        raise ValueError(f"{path}: unexpected TradingView status {record.get('status')!r}")
    if set(record.get("strategy_tester_results", {})) != TRADINGVIEW_SYMBOLS:
        raise ValueError(f"{path}: forward tester results must cover all default TradingView symbols")
    if set(record.get("chart_symbols", [])) != TRADINGVIEW_SYMBOLS:
        raise ValueError(f"{path}: recorded chart symbols do not match the default universe")
    for symbol, result in record["strategy_tester_results"].items():
        required_metrics = {
            "total_return_percent",
            "maximum_drawdown_percent",
            "profitable_trades_percent",
            "total_trades",
            "profit_factor",
        }
        missing = required_metrics.difference(result)
        if missing:
            raise ValueError(f"{path}: {symbol} is missing TradingView metrics: {sorted(missing)}")
        if result["total_trades"] <= 0:
            raise ValueError(f"{path}: {symbol} has no recorded TradingView trades")
    windows = record.get("research_windows", {})
    if windows.get("forward_2024_2026", {}).get("status") != "COMPLETED":
        raise ValueError(f"{path}: forward TradingView window is not complete")
    for window in ("validation_2020_2024", "development_2016_2020"):
        if windows.get(window, {}).get("status") != "DEFERRED_OUT_OF_SCOPE":
            raise ValueError(f"{path}: {window} must be explicitly deferred from validation scope")
    if record.get("published") is not False:
        raise ValueError(f"{path}: publication must remain false without an explicit user instruction")
    return record["status"]


def verify_repository() -> None:
    root = project_root()
    frames, manifest = load_market_data("configs/data.yaml")
    if set(frames) != {"BTCUSDT", "ETHUSDT", "SOLUSDT"}:
        raise ValueError(f"Unexpected default universe: {sorted(frames)}")
    if manifest["timeframe"] != "4h":
        raise ValueError("Minimum edge-research snapshot must use four-hour candles")
    if any(item["duplicates_removed"] < 0 for item in manifest["datasets"]):
        raise ValueError("Invalid duplicate-removal count")

    experiment_ids = []
    tradingview = {}
    for config_name in EXPERIMENT_CONFIGS:
        config = load_yaml(config_name)
        experiment_id = config["experiment_id"]
        experiment_ids.append(experiment_id)
        report = root / "reports" / f"{experiment_id}.md"
        summary = root / "reports" / f"{experiment_id}_summary.json"
        assets = root / "reports" / "assets" / experiment_id
        required_artifacts = (
            report,
            summary,
            assets / "results.json",
            assets / "trades.csv",
            assets / "equity_drawdown.png",
            assets / "trade_distribution.png",
        )
        missing = [str(path) for path in required_artifacts if not path.exists()]
        if missing:
            raise FileNotFoundError(f"{experiment_id}: missing artifacts: {missing}")
        summary_value = json.loads(summary.read_text())
        if summary_value["status"] != "COMPLETED":
            raise ValueError(f"{experiment_id}: Python experiment is not complete")
        pine_path = root / config["tradingview"]["pine_script"]
        verify_pine_contract(pine_path, config["experiment_type"])
        replication = root / "reports" / "tradingview" / f"{experiment_id}.json"
        tradingview[experiment_id] = (
            verify_tradingview_record(replication) if replication.exists() else "UNRECORDED"
        )

    registry = (root / "docs" / "experiment_registry.md").read_text()
    missing_registry = [experiment_id for experiment_id in experiment_ids if experiment_id not in registry]
    if missing_registry:
        raise ValueError(f"Experiment registry is missing: {missing_registry}")

    from .cross_asset_forward import forward_status, load_forward_config, read_ledger

    forward_config = load_forward_config(root / "configs" / "cross_asset_forward.yaml")
    forward_ledger = root / "forward" / "cross_asset_paper_ledger.jsonl"
    derived_forward_status = forward_status(read_ledger(forward_ledger), forward_config)
    recorded_forward_status = json.loads(
        (root / "forward" / "cross_asset_paper_status.json").read_text()
    )
    if recorded_forward_status != derived_forward_status:
        raise ValueError("Forward paper status does not match the verified append-only ledger")
    verify_cross_asset_pine_contract(
        root / "pine" / "btc_crypto_equity_residual_continuation.pine"
    )
    print(
        "Verified edge-research data, two completed Python experiments, reports, trade ledgers, "
        "charts, registry, Pine contracts, and the locked paper-forward ledger. "
        f"TradingView status: {tradingview}"
    )
