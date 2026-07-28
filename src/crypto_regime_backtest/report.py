from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from .config import STRATEGIES, Paths
from .regimes import REGIME_ORDER, load_regimes

COLORS = {
    "Crash/Capitulation": "#dc2626",
    "High Vol Expansion": "#f97316",
    "Bull Trend": "#16a34a",
    "Bear Trend": "#7c3aed",
    "Range/Chop": "#64748b",
}


def generate(paths: Paths) -> None:
    metrics = pd.read_csv(paths.results / "all_metrics.csv")
    provenance = pd.read_csv(paths.data / "provenance.csv")
    status = pd.read_csv(paths.results / "validation_status.csv")
    master = pd.read_csv(paths.results / "master_summary.csv", index_col=0)
    per_coin = pd.read_csv(paths.results / "per_coin_summary.csv")
    returns = pd.read_csv(
        paths.results / "strategy_daily_returns.csv", parse_dates=["timestamp"]
    ).set_index("timestamp")
    returns.index = pd.to_datetime(returns.index, utc=True)

    _regime_distribution(paths)
    _correlation(paths, returns)
    _equity_charts(paths, returns)

    report = _report_markdown(paths, metrics, provenance, status, master, per_coin)
    (paths.root / "REPORT.md").write_text(report)


def _regime_distribution(paths: Paths) -> None:
    values = {}
    for coin in sorted(pd.read_csv(paths.data / "provenance.csv")["coin"].unique()):
        regime = load_regimes(paths, coin)
        values[coin] = regime.loc[regime["warmup_complete"].astype(bool), "regime"].value_counts(
            normalize=True
        )
    frame = pd.DataFrame(values).T.reindex(columns=REGIME_ORDER).fillna(0) * 100
    ax = frame.plot(
        kind="bar", stacked=True, figsize=(14, 7), color=[COLORS[name] for name in REGIME_ORDER]
    )
    ax.set_title("Regime distribution by asset (finalized daily candles)")
    ax.set_ylabel("Percent of classified days")
    ax.set_xlabel("")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3)
    plt.tight_layout()
    plt.savefig(paths.charts / "regime_distribution.png", dpi=180)
    plt.close()


def _correlation(paths: Paths, returns: pd.DataFrame) -> None:
    correlation = returns.corr()
    plt.figure(figsize=(11, 9))
    sns.heatmap(correlation, cmap="vlag", center=0, vmin=-1, vmax=1, annot=True, fmt=".2f")
    plt.title("Strategy daily-return correlation")
    plt.tight_layout()
    plt.savefig(paths.charts / "strategy_correlation.png", dpi=180)
    plt.close()


def _equity_charts(paths: Paths, returns: pd.DataFrame) -> None:
    btc = load_regimes(paths, "BTC")
    availability = pd.Series(btc["regime"].to_numpy(), index=btc.index + pd.Timedelta(days=1))
    for strategy in STRATEGIES:
        plt.figure(figsize=(14, 6))
        ax = plt.gca()
        if strategy not in returns:
            ax.text(
                0.5,
                0.55,
                "NOT VALIDATED",
                ha="center",
                va="center",
                transform=ax.transAxes,
                fontsize=28,
                weight="bold",
                color="#dc2626",
            )
            ax.text(
                0.5,
                0.43,
                "Historical order-book, queue-position, and fill data were not available.",
                ha="center",
                va="center",
                transform=ax.transAxes,
                fontsize=11,
            )
            ax.set_axis_off()
        else:
            equity = 10_000 * (1 + returns[strategy].fillna(0)).cumprod()
            known = availability.reindex(equity.index, method="ffill")
            changes = known.ne(known.shift())
            starts = list(known.index[changes])
            for i, start in enumerate(starts):
                regime = known.loc[start]
                end = starts[i + 1] if i + 1 < len(starts) else known.index[-1]
                if regime in COLORS:
                    ax.axvspan(start, end, color=COLORS[regime], alpha=0.07, linewidth=0)
            ax.plot(equity.index, equity, color="#0f172a", linewidth=1.4)
            ax.set_ylabel("Equal-weight portfolio equity ($)")
            ax.grid(alpha=0.2)
        ax.set_title(f"{strategy.replace('_', ' ').title()} — historical research backtest")
        plt.tight_layout()
        plt.savefig(paths.charts / f"{strategy}_equity.png", dpi=180)
        plt.close()


def _report_markdown(
    paths: Paths,
    metrics: pd.DataFrame,
    provenance: pd.DataFrame,
    status: pd.DataFrame,
    master: pd.DataFrame,
    per_coin: pd.DataFrame,
) -> str:
    manifest = json.loads((paths.data / "manifest.json").read_text())
    best = per_coin[per_coin["sharpe_rank"] == 1].copy()
    best = best[["coin", "regime", "strategy", "sharpe", "max_drawdown", "total_return"]]
    source_table = provenance[
        [
            "coin",
            "timeframe",
            "kind",
            "source_symbols",
            "first_timestamp",
            "last_timestamp",
            "rows",
            "sha256",
        ]
    ]
    completed = metrics[
        (metrics["regime"] == "Overall") & (metrics["status"] == "completed_historical_backtest")
    ]
    top_overall = (
        completed.groupby("strategy", as_index=False)["sharpe"]
        .mean()
        .sort_values("sharpe", ascending=False)
    )
    combinations = _combinations(master)

    sections = [
        "# Crypto Regime & Strategy Validation Report",
        "",
        f"Pinned research window: `{manifest['window_start']}` to `{manifest['window_end_exclusive']}` (exclusive). Generated from committed artifacts. Synthetic data used: **{manifest['synthetic_data_used']}**.",
        "",
        "> This is historical research, not investment advice, a proven trading edge, or authorization for paper/live execution. A completed backtest means the code ran against the documented data under the documented assumptions; it does not establish future profitability.",
        "",
        "## Validation status",
        "",
        _markdown(status),
        "",
        "Market making is deliberately not scored: candles cannot establish executable two-sided fills, queue position, adverse selection, or hedging performance. Funding arbitrage uses real funding observations, but remains preliminary because borrow, basis drift, margin, liquidation, and venue-specific execution are not modeled.",
        "",
        "## Data sources and exact coverage",
        "",
        "All inputs came from Binance public spot OHLCV and USD-M funding endpoints. MATIC and POL are preserved as separate source symbols around Binance's migration; no missing candles were fabricated. Every committed compressed CSV has a SHA-256 digest below.",
        "",
        _markdown(source_table),
        "",
        "## Strategy × regime mean Sharpe",
        "",
        "Sharpe values are conditional historical estimates averaged across available assets. Costs are charged at 0.10% fees plus 0.05% slippage per one-way position change.",
        "",
        _markdown(master.reset_index().rename(columns={"index": "strategy"})),
        "",
        "## Per-asset best historical strategy by regime",
        "",
        _markdown(best),
        "",
        "## Overall historical ranking",
        "",
        _markdown(top_overall),
        "",
        "## Candidate regime-adaptive combinations",
        "",
        *[f"{i + 1}. {text}" for i, text in enumerate(combinations)],
        "",
        "These combinations are hypotheses derived from the same sample, not holdout-validated recommendations. They must be subjected to purged walk-forward testing, a sealed holdout, trial accounting, and robustness tests before any paper phase.",
        "",
        "## Charts",
        "",
        "![Regime distribution](charts/regime_distribution.png)",
        "",
        "![Strategy correlation](charts/strategy_correlation.png)",
        "",
    ]
    for strategy in STRATEGIES:
        sections.extend(
            [
                f"### {strategy.replace('_', ' ').title()}",
                "",
                f"![{strategy} equity](charts/{strategy}_equity.png)",
                "",
            ]
        )
    sections.extend(
        [
            "## Caveats and limitations",
            "",
            "- Results are in-sample over one pinned historical window; no sealed holdout claim is made.",
            "- Regime labels use completed daily bars and become available the following day. Range/Chop is the residual fifth class; `range_rule_matched` discloses when the strict ADX/Bollinger rule itself matched.",
            "- Signals execute no earlier than the next bar open. Bar data cannot resolve intrabar ordering or liquidity depth.",
            "- Fixed 0.15% one-way costs are intentionally simple and can understate stressed-market costs, borrow, spread, and market impact.",
            "- Momentum and statistical arbitrage are portfolio/pair strategies; per-asset rows are leg contributions, not standalone deployable strategies.",
            "- DCA spends $100 weekly from the fixed $10,000 starting cash until depleted; it does not assume unbounded external contributions.",
            "- Funding arbitrage excludes basis convergence/divergence, borrow availability and cost, collateral yield, liquidation, and transfer risk.",
            "- Survivorship bias remains because the requested universe is today's named set rather than a point-in-time investable universe.",
            "- POL combines non-overlapping MATICUSDT and POLUSDT exchange histories and retains the migration gap without interpolation.",
            "",
            "## Reproduce",
            "",
            "```bash",
            "uv sync --extra dev",
            "uv run crypto-regime-backtest verify",
            "uv run crypto-regime-backtest run",
            "uv run crypto-regime-backtest report",
            "```",
            "",
            "Use `uv run crypto-regime-backtest fetch --refresh` only when intentionally creating a new data snapshot; refreshed outputs will not match the committed checksums or report.",
        ]
    )
    return "\n".join(sections) + "\n"


def _combinations(master: pd.DataFrame) -> list[str]:
    candidates = []
    for regime in REGIME_ORDER:
        if regime not in master:
            continue
        ranking = master[regime].dropna().sort_values(ascending=False).head(2)
        if len(ranking):
            candidates.append(
                f"{regime}: " + " + ".join(name.replace("_", " ") for name in ranking.index)
            )
    if not candidates:
        return ["Unavailable: no completed metrics."]
    return [
        "; ".join(candidates),
        "Diversify the first-ranked regime specialists with the lowest-correlated eligible strategy.",
        "Use the top two per regime at half weight and require both to remain positive after doubled costs.",
    ]


def _markdown(frame: pd.DataFrame) -> str:
    display = frame.copy()
    for column in display.select_dtypes(include=["float"]).columns:
        display[column] = display[column].map(
            lambda value: "" if pd.isna(value) else f"{value:.4f}"
        )
    display = display.fillna("").astype(str)
    header = "| " + " | ".join(display.columns) + " |"
    separator = "| " + " | ".join("---" for _ in display.columns) + " |"
    rows = [
        "| " + " | ".join(value.replace("|", "\\|") for value in row) + " |"
        for row in display.to_numpy()
    ]
    return "\n".join([header, separator, *rows])
