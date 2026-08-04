from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .config import resolve_from_root
from .engine import EngineResult
from .metrics import equity_drawdown


def write_report(payload: dict[str, Any], result: EngineResult) -> Path:
    report_root = resolve_from_root(payload.get("report_directory", "reports"))
    asset_root = report_root / "assets" / payload["experiment_id"]
    asset_root.mkdir(parents=True, exist_ok=True)
    _equity_and_drawdown_chart(result, asset_root / "equity_drawdown.png")
    _trade_distribution_chart(result.trades, asset_root / "trade_distribution.png")
    result.trades.to_csv(asset_root / "trades.csv", index=False)
    (asset_root / "results.json").write_text(
        json.dumps(_json_safe(payload["machine_results"]), indent=2) + "\n"
    )

    relative_assets = f"assets/{payload['experiment_id']}"
    sections = [
        f"# {payload['strategy_name']}",
        "",
        f"**Experiment:** `{payload['experiment_id']}`",
        "",
        f"**Verdict:** **{payload['verdict']}**",
        "",
        f"**Primary metric:** {payload['primary_metric']}",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Economic reasoning",
        "",
        payload["economic_reasoning"],
        "",
        "## Exact rules",
        "",
        *[f"- {rule}" for rule in payload["rules"]],
        "",
        "## Data period and quality",
        "",
        payload["data_description"],
        "",
        _markdown_table(payload["data_quality"]),
        "",
        "## Cost and sizing assumptions",
        "",
        payload["cost_description"],
        "",
        "## Main results",
        "",
        _markdown_table(payload["main_results"]),
        "",
        f"![Equity and drawdown]({relative_assets}/equity_drawdown.png)",
        "",
        f"![Trade-return distribution]({relative_assets}/trade_distribution.png)",
        "",
        "## Results by asset",
        "",
        _markdown_table(payload["results_by_asset"]),
        "",
        "## Results by time period",
        "",
        _markdown_table(payload["results_by_period"]),
        "",
        "## Baseline comparison",
        "",
        _markdown_table(payload["baselines"]),
        "",
        "## Parameter and family comparison",
        "",
        _markdown_table(payload["variants"]),
        "",
        "## Robustness and attempted falsification",
        "",
        _markdown_table(payload["robustness"]),
        "",
        "## Pine/TradingView handoff (supplementary)",
        "",
        payload.get(
            "tradingview_status",
            "DEFERRED — Python is the validation authority; the Pine artifact is available for later TradingView review.",
        ),
        "",
        f"Pine strategy: [`{payload.get('pine_script', 'not configured')}`](../{payload.get('pine_script', '')})",
        "",
    ]
    if payload.get("largest_trades") is not None:
        sections.extend(
            [
                "## Largest wins and losses reviewed",
                "",
                _markdown_table(payload["largest_trades"]),
                "",
                payload.get(
                    "largest_trade_review",
                    "The ledger was checked for timestamp order, finite prices, and declared exit reasons.",
                ),
                "",
            ]
        )
    sections.extend(
        [
            "## Known limitations",
            "",
            *[f"- {item}" for item in payload["limitations"]],
            "",
            "## Verdict",
            "",
            f"**{payload['verdict']}** — {payload['verdict_reason']}",
            "",
            "## Next justified experiment",
            "",
            payload["next_experiment"],
            "",
            "## Reproduce",
            "",
            "```bash",
            payload.get(
                "reproduce_command", f"edge-research run --config {payload['config_path']}"
            ),
            "```",
            "",
            "This is historical research, not investment advice or authorization for paper/live trading.",
        ]
    )
    report_path = report_root / f"{payload['experiment_id']}.md"
    report_path.write_text("\n".join(sections) + "\n")
    _write_summary(payload, report_path)
    update_registry(report_root)
    return report_path


def _equity_and_drawdown_chart(result: EngineResult, destination: Path) -> None:
    values = equity_drawdown(result.returns, float(result.equity.iloc[0]) if len(result.equity) else 10_000)
    figure, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True, height_ratios=[2, 1])
    axes[0].plot(values.index, values["equity"], color="#0f172a", linewidth=1.2)
    axes[0].set_title("Portfolio equity after fees and slippage")
    axes[0].set_ylabel("Equity")
    axes[0].grid(alpha=0.2)
    axes[1].fill_between(values.index, values["drawdown"], 0, color="#dc2626", alpha=0.55)
    axes[1].set_title("Drawdown")
    axes[1].set_ylabel("Return")
    axes[1].grid(alpha=0.2)
    figure.tight_layout()
    figure.savefig(destination, dpi=170)
    plt.close(figure)


def _trade_distribution_chart(trades: pd.DataFrame, destination: Path) -> None:
    figure, axis = plt.subplots(figsize=(10, 5))
    if trades.empty:
        axis.text(0.5, 0.5, "No completed trades", ha="center", va="center")
        axis.set_axis_off()
    else:
        values = pd.to_numeric(trades["net_return"], errors="coerce").dropna() * 100
        bins = min(40, max(10, int(np.sqrt(len(values)) * 2)))
        axis.hist(values, bins=bins, color="#334155", alpha=0.85)
        axis.axvline(0, color="#dc2626", linewidth=1)
        axis.set_xlabel("Net trade return (%)")
        axis.set_ylabel("Trades")
        axis.set_title("Completed-trade return distribution")
        axis.grid(alpha=0.15)
    figure.tight_layout()
    figure.savefig(destination, dpi=170)
    plt.close(figure)


def _write_summary(payload: dict[str, Any], report_path: Path) -> None:
    summary = {
        "experiment_id": payload["experiment_id"],
        "date": datetime.now(UTC).date().isoformat(),
        "hypothesis": payload["hypothesis"],
        "dataset": payload["data_description"],
        "status": "COMPLETED",
        "primary_result": payload["primary_result"],
        "verdict": payload["verdict"],
        "report_path": str(report_path.relative_to(resolve_from_root("."))),
        "follow_up_question": payload["next_experiment"],
    }
    report_path.with_name(f"{payload['experiment_id']}_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )


def update_registry(report_root: Path) -> None:
    summaries = []
    for path in sorted(report_root.glob("*_summary.json")):
        summaries.append(json.loads(path.read_text()))
    rows = [
        {
            "Experiment ID": item["experiment_id"],
            "Date": item["date"],
            "Hypothesis": item["hypothesis"],
            "Dataset": item["dataset"],
            "Status": item["status"],
            "Primary result": item["primary_result"],
            "Verdict": item["verdict"],
            "Pine/TradingView handoff": _tradingview_registry_evidence(item["experiment_id"]),
            "Report": f"[{item['report_path']}]({Path('..') / item['report_path']})",
            "Follow-up question": item["follow_up_question"],
        }
        for item in summaries
    ]
    frame = pd.DataFrame(rows)
    header = [
        "# Experiment Registry",
        "",
        "Completed and failed experiments are permanent research evidence. Re-running an experiment with the same ID replaces its generated artifacts but not its declared hypothesis.",
        "",
        _markdown_table(frame),
        "",
    ]
    resolve_from_root("docs/experiment_registry.md").write_text("\n".join(header))


def _tradingview_registry_evidence(experiment_id: str) -> str:
    path = resolve_from_root(f"reports/tradingview/{experiment_id}.json")
    if not path.exists():
        return "Deferred; Python validation complete"
    record = json.loads(path.read_text())
    runs = record.get("strategy_tester_results", {})
    if not runs:
        return record.get("status", "Deferred; Python validation complete")
    returns = ", ".join(
        f"{symbol.split(':')[-1].replace('USDT', '')} {result['total_return_percent']:+.2f}%"
        for symbol, result in runs.items()
    )
    deferred = any(
        value.get("status") == "DEFERRED_OUT_OF_SCOPE"
        for value in record.get("research_windows", {}).values()
    )
    suffix = "; historical TradingView windows deferred, Python validation complete" if deferred else ""
    return f"Pine compiled; forward {returns}{suffix}."


def _markdown_table(frame: pd.DataFrame | list[dict[str, Any]] | dict[str, Any]) -> str:
    if isinstance(frame, dict):
        frame = pd.DataFrame([frame])
    elif isinstance(frame, list):
        frame = pd.DataFrame(frame)
    if frame is None or frame.empty:
        return "_No observations._"
    display = frame.copy()
    for column in display.columns:
        display[column] = display[column].map(_display_value)
    header = "| " + " | ".join(str(column) for column in display.columns) + " |"
    separator = "| " + " | ".join("---" for _ in display.columns) + " |"
    rows = [
        "| " + " | ".join(str(value).replace("|", "\\|") for value in row) + " |"
        for row in display.to_numpy()
    ]
    return "\n".join([header, separator, *rows])


def _display_value(value: Any) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "—"
    if isinstance(value, (float, np.floating)):
        return f"{float(value):.4f}"
    return str(value)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, pd.DataFrame):
        return [_json_safe(item) for item in value.to_dict(orient="records")]
    if isinstance(value, pd.Series):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value
