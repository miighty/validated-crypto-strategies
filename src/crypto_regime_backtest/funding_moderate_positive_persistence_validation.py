from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .config import ONE_WAY_COST, Paths, STARTING_CAPITAL
from .funding_negative_panel_validation import (
    AssetFrames,
    BENCHMARK_ASSETS,
    CONTRIBUTION_HOUR_UTC,
    RANDOM_SEED,
    UNIVERSE,
    classify_verdict,
    dataframe_to_markdown,
    load_market_data,
    provenance,
    remove_best_trade,
    simulate_always_long_schedule,
    simulate_cash_reserve,
    simulate_daily_asset_dca,
    simulate_equal_weight_dca,
    simulate_random_baseline,
    simulate_signal_strategy,
)

SAMPLE_START = pd.Timestamp("2021-01-01T00:00:00Z")
VALIDATION_START = pd.Timestamp("2024-01-01T00:00:00Z")
HOLDOUT_START = pd.Timestamp("2025-01-01T00:00:00Z")
PRIMARY_MIN_THRESHOLD = 0.0001
PRIMARY_MAX_THRESHOLD = 0.0005
PRIMARY_HOLD_HOURS = 8
PRIMARY_COOLDOWN_HOURS = 24
SENSITIVITY_MIN_THRESHOLDS = (0.0, 0.0002)
SENSITIVITY_MAX_THRESHOLDS = (0.0003, 0.0005, 0.00075)
SENSITIVITY_HOLDS = (8, 16, 24)
BUCKETS = (
    ("le_-5bps", -np.inf, -0.0005),
    ("-5_to_-1bps", -0.0005, -0.0001),
    ("-1_to_+1bps", -0.0001, 0.0001),
    ("+1_to_+5bps", 0.0001, 0.0005),
    ("ge_+5bps", 0.0005, np.inf),
)


@dataclass(frozen=True)
class StrategySpec:
    name: str
    min_funding_threshold: float
    max_funding_threshold: float
    hold_hours: int
    cooldown_hours: int


@dataclass(frozen=True)
class StudyConfig:
    sample_start: str = "2021-01-01T00:00:00Z"
    validation_start: str = "2024-01-01T00:00:00Z"
    holdout_start: str = "2025-01-01T00:00:00Z"
    contribution_hour_utc: int = CONTRIBUTION_HOUR_UTC
    initial_capital: float = STARTING_CAPITAL
    one_way_cost: float = ONE_WAY_COST
    primary_min_threshold: float = PRIMARY_MIN_THRESHOLD
    primary_max_threshold: float = PRIMARY_MAX_THRESHOLD
    primary_hold_hours: int = PRIMARY_HOLD_HOURS
    primary_cooldown_hours: int = PRIMARY_COOLDOWN_HOURS
    primary_rule: str = (
        "At each completed Binance 8h funding print from the nine-asset spot universe, if one or more assets "
        "have MODERATELY positive funding in the preregistered +1 to +5 bps bucket, select the single most "
        "positive asset below +5 bps, enter spot long at the next hourly open with the full accrued reserve, "
        "hold 8h, then exit at the close and remain in cash for a 24h cooldown."
    )


def run_funding_moderate_positive_persistence_validation(
    paths: Paths, seed: int = RANDOM_SEED
) -> pd.DataFrame:
    paths.create()
    run_id = pd.Timestamp.now(tz="UTC").strftime("run-%Y%m%dT%H%M%SZ")
    output = paths.results / "funding_moderate_positive_persistence" / "runs" / run_id
    output.mkdir(parents=True, exist_ok=False)

    config = StudyConfig()
    spec = StrategySpec(
        name="moderate_positive_funding_persistence_panel",
        min_funding_threshold=config.primary_min_threshold,
        max_funding_threshold=config.primary_max_threshold,
        hold_hours=config.primary_hold_hours,
        cooldown_hours=config.primary_cooldown_hours,
    )
    market = load_market_data(paths, config.sample_start)
    schedule = build_daily_contribution_schedule(
        market["BTC"].price, config.initial_capital, config.contribution_hour_utc
    )
    final_closes = {asset: float(frames.price["close"].iloc[-1]) for asset, frames in market.items()}

    signal_panel = build_signal_panel(market, spec)
    cash = simulate_cash_reserve(market["BTC"].price, schedule, final_closes)
    daily_benchmarks = [
        simulate_daily_asset_dca(market[asset].price, schedule, config.one_way_cost, final_closes, asset)
        for asset in BENCHMARK_ASSETS
    ]
    equal_weight_daily = simulate_equal_weight_dca(
        market, schedule, config.one_way_cost, final_closes, cadence="daily"
    )
    equal_weight_weekly = simulate_equal_weight_dca(
        market, schedule, config.one_way_cost, final_closes, cadence="weekly"
    )
    primary = simulate_signal_strategy(
        market, schedule, config.one_way_cost, final_closes, signal_panel, spec.name
    )
    always_long = simulate_always_long_schedule(
        market, schedule, config.one_way_cost, final_closes, signal_panel
    )
    random_baseline = simulate_random_baseline(
        market, schedule, config.one_way_cost, final_closes, signal_panel, seed
    )

    sensitivity = run_sensitivity_suite(market, schedule, config.one_way_cost, final_closes)
    hostile = run_hostile_checks(
        market,
        schedule,
        config.one_way_cost,
        final_closes,
        signal_panel,
        primary.summary,
        seed,
    )
    bucket_forward = build_bucket_forward_return_panel(market, config.one_way_cost)
    verdict = classify_verdict(primary.summary, daily_benchmarks, equal_weight_daily.summary, hostile)
    primary.summary["verdict"] = verdict

    summary_frame = pd.DataFrame(
        [
            cash.summary,
            *[item.summary for item in daily_benchmarks],
            equal_weight_daily.summary,
            equal_weight_weekly.summary,
            always_long.summary,
            random_baseline.summary,
            primary.summary,
        ]
    )
    trade_log = pd.concat(
        [
            cash.ledger.assign(strategy="cash_reserve"),
            *[item.ledger.assign(strategy=str(item.summary["strategy"])) for item in daily_benchmarks],
            equal_weight_daily.ledger.assign(strategy="daily_equal_weight_universe_dca"),
            equal_weight_weekly.ledger.assign(strategy="weekly_equal_weight_universe_dca"),
            always_long.ledger.assign(strategy="always_long_equal_weight_schedule"),
            random_baseline.ledger.assign(strategy="random_asset_schedule_baseline"),
            primary.ledger.assign(strategy=spec.name),
        ],
        ignore_index=True,
    )
    equity_curve = pd.concat(
        [
            cash.equity.assign(strategy="cash_reserve"),
            *[item.equity.assign(strategy=str(item.summary["strategy"])) for item in daily_benchmarks],
            equal_weight_daily.equity.assign(strategy="daily_equal_weight_universe_dca"),
            equal_weight_weekly.equity.assign(strategy="weekly_equal_weight_universe_dca"),
            always_long.equity.assign(strategy="always_long_equal_weight_schedule"),
            random_baseline.equity.assign(strategy="random_asset_schedule_baseline"),
            primary.equity.assign(strategy=spec.name),
        ],
        ignore_index=True,
    )
    partition_frame = pd.concat(
        [
            cash.partition_summary.assign(strategy="cash_reserve"),
            *[
                item.partition_summary.assign(strategy=str(item.summary["strategy"]))
                for item in daily_benchmarks
            ],
            equal_weight_daily.partition_summary.assign(strategy="daily_equal_weight_universe_dca"),
            equal_weight_weekly.partition_summary.assign(strategy="weekly_equal_weight_universe_dca"),
            always_long.partition_summary.assign(strategy="always_long_equal_weight_schedule"),
            random_baseline.partition_summary.assign(strategy="random_asset_schedule_baseline"),
            primary.partition_summary.assign(strategy=spec.name),
        ],
        ignore_index=True,
    )

    summary_frame.to_csv(output / "strategy_summary.csv", index=False, float_format="%.17g")
    trade_log.to_csv(output / "trade_log.csv", index=False, float_format="%.17g")
    equity_curve.to_csv(output / "equity_curves.csv", index=False, float_format="%.17g")
    partition_frame.to_csv(output / "partition_summary.csv", index=False, float_format="%.17g")
    signal_panel.to_csv(output / "signal_panel.csv", index=False, float_format="%.17g")
    sensitivity.to_csv(output / "sensitivity_checks.csv", index=False, float_format="%.17g")
    hostile.to_csv(output / "hostile_checks.csv", index=False, float_format="%.17g")
    bucket_forward.to_csv(output / "bucket_forward_returns.csv", index=False, float_format="%.17g")

    manifest = {
        "config": asdict(config),
        "spec": asdict(spec),
        "assets": {asset: provenance(paths, asset) for asset in UNIVERSE},
        "raw_signal_count": int(len(signal_panel)),
        "sample_start": market["BTC"].price["timestamp"].min().isoformat(),
        "sample_end": market["BTC"].price["timestamp"].max().isoformat(),
    }
    (output / "config.json").write_text(json.dumps(manifest, indent=2) + "\n")
    write_report(output, manifest, summary_frame, hostile, bucket_forward)
    print(f"Funding-moderate-positive persistence validation written to {output}", flush=True)
    return summary_frame


def build_daily_contribution_schedule(
    frame: pd.DataFrame, initial_capital: float, contribution_hour_utc: int
) -> pd.Series:
    slots = frame.loc[frame["timestamp"].dt.hour == contribution_hour_utc, "timestamp"]
    if slots.empty:
        raise RuntimeError("No contribution slots available in BTC 1h sample")
    tranche = initial_capital / len(slots)
    return pd.Series(tranche, index=slots, name="contribution_usd")


def build_signal_panel(market: dict[str, AssetFrames], spec: StrategySpec) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for asset, frames in market.items():
        funding = frames.funding.copy()
        funding = funding.loc[
            (funding["funding_rate"] >= spec.min_funding_threshold)
            & (funding["funding_rate"] < spec.max_funding_threshold)
        ].copy()
        if funding.empty:
            continue
        price_index = frames.price.set_index("timestamp").index
        funding["entry_time"] = funding["timestamp"] + pd.Timedelta(hours=1)
        funding["exit_time"] = funding["entry_time"] + pd.Timedelta(hours=spec.hold_hours)
        funding = funding.loc[
            funding["entry_time"].isin(price_index) & funding["exit_time"].isin(price_index)
        ].copy()
        if funding.empty:
            continue
        for row in funding.itertuples(index=False):
            rows.append(
                {
                    "signal_time": pd.Timestamp(row.timestamp),
                    "entry_time": pd.Timestamp(row.entry_time),
                    "exit_time": pd.Timestamp(row.exit_time),
                    "asset": asset,
                    "funding_rate": float(row.funding_rate),
                    "mark_price": float(row.mark_price) if pd.notna(row.mark_price) else np.nan,
                    "source_symbol": str(row.source_symbol),
                }
            )
    if not rows:
        return pd.DataFrame(
            columns=[
                "signal_time",
                "entry_time",
                "exit_time",
                "asset",
                "funding_rate",
                "mark_price",
                "source_symbol",
            ]
        )
    panel = pd.DataFrame(rows).sort_values(
        ["entry_time", "funding_rate", "asset"], ascending=[True, False, True]
    ).reset_index(drop=True)
    chosen: list[dict[str, object]] = []
    next_ok = pd.Timestamp.min.tz_localize("UTC")
    for _, same_time in panel.groupby("entry_time", sort=True):
        best = same_time.sort_values(["funding_rate", "asset"], ascending=[False, True]).iloc[0]
        entry = pd.Timestamp(best["entry_time"])
        if entry < next_ok:
            continue
        chosen.append(best.to_dict())
        next_ok = pd.Timestamp(best["exit_time"]) + pd.Timedelta(hours=spec.cooldown_hours)
    chosen_frame = pd.DataFrame(chosen)
    if chosen_frame.empty:
        return chosen_frame.reindex(columns=panel.columns)
    return chosen_frame.sort_values("entry_time").reset_index(drop=True)


def run_sensitivity_suite(
    market: dict[str, AssetFrames],
    schedule: pd.Series,
    one_way_cost: float,
    final_closes: dict[str, float],
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    seen: set[tuple[float, float, int]] = set()
    for min_threshold in (PRIMARY_MIN_THRESHOLD, *SENSITIVITY_MIN_THRESHOLDS):
        for max_threshold in SENSITIVITY_MAX_THRESHOLDS:
            for hold_hours in SENSITIVITY_HOLDS:
                key = (min_threshold, max_threshold, hold_hours)
                if key in seen or min_threshold >= max_threshold:
                    continue
                seen.add(key)
                spec = StrategySpec(
                    name=(
                        f"min_{min_threshold:.4f}_max_{max_threshold:.4f}_hold_{hold_hours}h"
                    ),
                    min_funding_threshold=min_threshold,
                    max_funding_threshold=max_threshold,
                    hold_hours=hold_hours,
                    cooldown_hours=PRIMARY_COOLDOWN_HOURS,
                )
                signals = build_signal_panel(market, spec)
                result = simulate_signal_strategy(
                    market, schedule, one_way_cost, final_closes, signals, spec.name
                )
                rows.append(
                    {
                        "min_threshold": min_threshold,
                        "max_threshold": max_threshold,
                        "hold_hours": hold_hours,
                        "trade_count": int(result.summary["event_count"]),
                        "terminal_value": float(result.summary["terminal_value"]),
                        "net_return": float(result.summary["net_return"]),
                        "avg_trade_return": float(result.summary["avg_trade_return"]),
                        "win_rate": float(result.summary["win_rate"]),
                    }
                )
    return pd.DataFrame(rows).sort_values(
        ["min_threshold", "max_threshold", "hold_hours"]
    ).reset_index(drop=True)


def run_hostile_checks(
    market: dict[str, AssetFrames],
    schedule: pd.Series,
    one_way_cost: float,
    final_closes: dict[str, float],
    signals: pd.DataFrame,
    primary_summary: dict[str, object],
    seed: int,
) -> pd.DataFrame:
    doubled_cost = simulate_signal_strategy(
        market,
        schedule,
        one_way_cost * 2,
        final_closes,
        signals,
        "moderate_positive_funding_persistence_panel_doubled_cost",
    )
    without_best = remove_best_trade(market, schedule, one_way_cost, final_closes, signals)
    random_baseline = simulate_random_baseline(market, schedule, one_way_cost, final_closes, signals, seed)
    return pd.DataFrame(
        [
            {
                "check": "doubled_cost",
                "terminal_value": float(doubled_cost.summary["terminal_value"]),
                "net_return": float(doubled_cost.summary["net_return"]),
                "beats_primary": float(doubled_cost.summary["terminal_value"])
                >= float(primary_summary["terminal_value"]),
            },
            {
                "check": "exclude_best_trade",
                "terminal_value": float(without_best.summary["terminal_value"]),
                "net_return": float(without_best.summary["net_return"]),
                "beats_primary": float(without_best.summary["terminal_value"])
                >= float(primary_summary["terminal_value"]),
            },
            {
                "check": "random_baseline",
                "terminal_value": float(random_baseline.summary["terminal_value"]),
                "net_return": float(random_baseline.summary["net_return"]),
                "beats_primary": float(random_baseline.summary["terminal_value"])
                >= float(primary_summary["terminal_value"]),
            },
        ]
    )


def build_bucket_forward_return_panel(
    market: dict[str, AssetFrames], one_way_cost: float
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    horizons = (8, 16, 24)
    for asset, frames in market.items():
        price_map = frames.price.set_index("timestamp")[["open", "close"]]
        price_index = price_map.index
        funding = frames.funding.copy()
        funding["entry_time"] = funding["timestamp"] + pd.Timedelta(hours=1)
        for label, lower, upper in BUCKETS:
            bucket = funding.loc[
                (funding["funding_rate"] >= lower) & (funding["funding_rate"] < upper)
            ].copy()
            if bucket.empty:
                continue
            for horizon in horizons:
                bucket_h = bucket.copy()
                bucket_h["exit_time"] = bucket_h["entry_time"] + pd.Timedelta(hours=horizon)
                bucket_h = bucket_h.loc[
                    bucket_h["entry_time"].isin(price_index) & bucket_h["exit_time"].isin(price_index)
                ].copy()
                if bucket_h.empty:
                    continue
                gross_returns = []
                net_returns = []
                holdout_gross_returns = []
                for row in bucket_h.itertuples(index=False):
                    entry_time = pd.Timestamp(row.entry_time)
                    exit_time = pd.Timestamp(row.exit_time)
                    entry_open = float(price_map.at[entry_time, "open"])
                    exit_close = float(price_map.at[exit_time, "close"])
                    gross = exit_close / entry_open - 1
                    net = gross - 2 * one_way_cost
                    gross_returns.append(gross)
                    net_returns.append(net)
                    if entry_time >= HOLDOUT_START:
                        holdout_gross_returns.append(gross)
                rows.append(
                    {
                        "asset": asset,
                        "bucket": label,
                        "horizon_hours": horizon,
                        "sample_count": int(len(bucket_h)),
                        "avg_gross_return": float(np.mean(gross_returns)),
                        "avg_net_return": float(np.mean(net_returns)),
                        "win_rate_gross": float(np.mean(np.array(gross_returns) > 0)),
                        "holdout_count_2025_onward": int(len(holdout_gross_returns)),
                        "holdout_avg_gross_return": (
                            float(np.mean(holdout_gross_returns))
                            if holdout_gross_returns
                            else np.nan
                        ),
                    }
                )
    frame = pd.DataFrame(rows)
    pooled_rows: list[dict[str, object]] = []
    if not frame.empty:
        for (bucket, horizon), group in frame.groupby(["bucket", "horizon_hours"], sort=False):
            pooled_rows.append(
                {
                    "asset": "ALL",
                    "bucket": bucket,
                    "horizon_hours": int(horizon),
                    "sample_count": int(group["sample_count"].sum()),
                    "avg_gross_return": float(
                        np.average(group["avg_gross_return"], weights=group["sample_count"])
                    ),
                    "avg_net_return": float(
                        np.average(group["avg_net_return"], weights=group["sample_count"])
                    ),
                    "win_rate_gross": float(
                        np.average(group["win_rate_gross"], weights=group["sample_count"])
                    ),
                    "holdout_count_2025_onward": int(group["holdout_count_2025_onward"].sum()),
                    "holdout_avg_gross_return": float(
                        np.average(
                            group["holdout_avg_gross_return"].fillna(0.0),
                            weights=group["holdout_count_2025_onward"].clip(lower=0),
                        )
                    )
                    if int(group["holdout_count_2025_onward"].sum()) > 0
                    else np.nan,
                }
            )
    pooled = pd.DataFrame(pooled_rows)
    if pooled.empty:
        return frame
    return pd.concat([pooled, frame], ignore_index=True)


def write_report(
    output: Path,
    manifest: dict[str, object],
    summary: pd.DataFrame,
    hostile: pd.DataFrame,
    bucket_forward: pd.DataFrame,
) -> None:
    primary = summary.loc[
        summary["strategy"].eq("moderate_positive_funding_persistence_panel")
    ].iloc[0]
    baselines = summary.loc[
        summary["strategy"].isin(
            [
                "daily_btc_dca",
                "daily_eth_dca",
                "daily_sol_dca",
                "daily_xrp_dca",
                "daily_equal_weight_universe_dca",
            ]
        )
    ]
    pooled_bucket = bucket_forward.loc[
        (bucket_forward["asset"] == "ALL")
        & (bucket_forward["bucket"] == "+1_to_+5bps")
        & (bucket_forward["horizon_hours"] == PRIMARY_HOLD_HOURS)
    ].copy()
    zero_bucket = bucket_forward.loc[
        (bucket_forward["asset"] == "ALL")
        & (bucket_forward["bucket"] == "-1_to_+1bps")
        & (bucket_forward["horizon_hours"] == PRIMARY_HOLD_HOURS)
    ].copy()
    pooled_row = pooled_bucket.iloc[0] if not pooled_bucket.empty else None
    zero_row = zero_bucket.iloc[0] if not zero_bucket.empty else None
    lines = [
        "# Moderate positive funding persistence validation",
        "",
        f"Run artifact: `{output / 'REPORT.md'}`",
        "",
        "## Key findings",
        "",
        "- **Primary rule tested:** across real Binance funding for **BTC / ETH / SOL / XRP / BNB / ADA / DOGE / AVAX / LINK**, if one or more completed 8h funding prints land in the preregistered **+1 to +5 bps** bucket, select the **single most positive** asset below +5 bps, enter **spot long at the next hourly open**, hold **8h**, then exit and wait **24h** before the next trade.",
        "- **Why this is genuinely new:** prior studies tested **negative funding mean reversion** (<= -5 bps) and **extreme positive funding persistence** (>= +5 bps). This run isolates the middle regime where crowded carry may still persist before becoming too crowded.",
        "- **Benchmarks:** same fixed **$10,000** reserve released as equal daily contributions, compared against **daily BTC, ETH, SOL, and XRP DCA** plus a **daily equal-weight nine-asset universe DCA**.",
        "",
        "## Result table",
        "",
        dataframe_to_markdown(
            summary[["strategy", "terminal_value", "event_count", "avg_trade_return", "win_rate"]]
        ),
        "",
        "## Bucket diagnostic",
        "",
        dataframe_to_markdown(
            bucket_forward.loc[
                (bucket_forward["asset"] == "ALL")
                & (bucket_forward["horizon_hours"].isin([8, 16, 24]))
            ][
                [
                    "asset",
                    "bucket",
                    "horizon_hours",
                    "sample_count",
                    "avg_gross_return",
                    "avg_net_return",
                    "holdout_count_2025_onward",
                    "holdout_avg_gross_return",
                ]
            ]
        ),
        "",
        "## Honest conclusion",
        "",
        (
            f"> **{primary['verdict']}.** The moderate-positive-funding panel finished at "
            f"**${primary['terminal_value']:.2f}** across **{int(primary['event_count'])} trades**. "
            f"Best required baseline finished at **${baselines['terminal_value'].max():.2f}**."
        ),
        (
            f"> Pooled +1 to +5 bps forward 8h return averaged **{float(pooled_row['avg_gross_return']) * 100:.3f}% gross** "
            f"and **{float(pooled_row['avg_net_return']) * 100:.3f}% net** per event"
            if pooled_row is not None
            else "> No pooled +1 to +5 bps bucket rows were available."
        ),
        (
            f"> Zero-funding bucket averaged **{float(zero_row['avg_gross_return']) * 100:.3f}% gross** over the same 8h horizon."
            if zero_row is not None
            else "> No pooled zero-funding bucket rows were available."
        ),
        "",
        "## Decisive hostile checks",
        "",
        dataframe_to_markdown(hostile),
        "",
        "## Files",
        "",
        f"- `{output / 'strategy_summary.csv'}`",
        f"- `{output / 'trade_log.csv'}`",
        f"- `{output / 'equity_curves.csv'}`",
        f"- `{output / 'partition_summary.csv'}`",
        f"- `{output / 'signal_panel.csv'}`",
        f"- `{output / 'sensitivity_checks.csv'}`",
        f"- `{output / 'hostile_checks.csv'}`",
        f"- `{output / 'bucket_forward_returns.csv'}`",
        "",
        "## Manifest excerpt",
        "",
        "```json",
        json.dumps({"spec": manifest["spec"], "raw_signal_count": manifest["raw_signal_count"]}, indent=2),
        "```",
    ]
    (output / "REPORT.md").write_text("\n".join(lines) + "\n")
