from __future__ import annotations

import json
from collections import defaultdict

import numpy as np
import pandas as pd

from .backtest import BacktestResult, execute_positions, execute_return_stream
from .config import COINS, ONE_WAY_COST, PERIODS_PER_YEAR, STARTING_CAPITAL, Paths
from .data import load_ohlcv
from .regimes import REGIME_ORDER, load_regimes, regimes_known_at
from .strategies import (
    breakout,
    contrarian,
    grid,
    mean_reversion,
    momentum_positions,
    statistical_arbitrage,
    trend_following,
)

PAIR_DEFINITIONS = (
    ("BTC", "ETH"),
    ("SOL", "AVAX"),
    ("LINK", "POL"),
    ("BNB", "XRP"),
    ("ADA", "DOGE"),
)


def run(paths: Paths) -> pd.DataFrame:
    paths.create()
    all_metrics: list[dict[str, object]] = []
    daily_returns: dict[str, dict[str, pd.Series]] = defaultdict(dict)
    regimes = {coin: load_regimes(paths, coin) for coin in COINS}
    daily_frames = {coin: load_ohlcv(paths, coin, "1d") for coin in COINS}

    directional = {
        "trend_following": ("1d", trend_following),
        "mean_reversion": ("4h", mean_reversion),
        "breakout": ("4h", breakout),
        "grid": ("1h", grid),
        "contrarian": ("1d", contrarian),
    }
    for strategy, (timeframe, signal_function) in directional.items():
        for coin in COINS:
            print(f"Running {strategy} on {coin}...", flush=True)
            frame = load_ohlcv(paths, coin, timeframe)
            known_regimes = regimes_known_at(frame.index, regimes[coin])
            result = execute_positions(
                frame,
                signal_function(frame),
                known_regimes,
                PERIODS_PER_YEAR[timeframe],
            )
            _save_result(paths, strategy, coin, result)
            all_metrics.extend(_tag_metrics(result.metrics, strategy, coin, timeframe))
            daily_returns[strategy][coin] = _to_daily(result.returns)

    momentum = momentum_positions(daily_frames)
    for coin, desired in momentum.items():
        known_regimes = regimes_known_at(daily_frames[coin].index, regimes[coin])
        result = execute_positions(
            daily_frames[coin], desired, known_regimes, PERIODS_PER_YEAR["1d"]
        )
        _save_result(paths, "momentum", coin, result)
        all_metrics.extend(_tag_metrics(result.metrics, "momentum", coin, "1d"))
        daily_returns["momentum"][coin] = _to_daily(result.returns)

    for first_coin, second_coin in PAIR_DEFINITIONS:
        first = load_ohlcv(paths, first_coin, "4h")
        second = load_ohlcv(paths, second_coin, "4h")
        first_desired, second_desired = statistical_arbitrage(first, second)
        for coin, frame, desired in (
            (first_coin, first, first_desired),
            (second_coin, second, second_desired),
        ):
            known_regimes = regimes_known_at(frame.index, regimes[coin])
            result = execute_positions(frame, desired, known_regimes, PERIODS_PER_YEAR["4h"])
            _save_result(paths, "statistical_arbitrage", coin, result)
            all_metrics.extend(_tag_metrics(result.metrics, "statistical_arbitrage", coin, "4h"))
            daily_returns["statistical_arbitrage"][coin] = _to_daily(result.returns)

    for coin in COINS:
        dca_result = _run_dca(
            daily_frames[coin], regimes_known_at(daily_frames[coin].index, regimes[coin])
        )
        _save_result(paths, "dca", coin, dca_result)
        all_metrics.extend(_tag_metrics(dca_result.metrics, "dca", coin, "1d"))
        daily_returns["dca"][coin] = _to_daily(dca_result.returns)

        funding_result = _run_funding(paths, coin, regimes[coin])
        _save_result(paths, "funding_arbitrage", coin, funding_result)
        all_metrics.extend(_tag_metrics(funding_result.metrics, "funding_arbitrage", coin, "8h"))
        daily_returns["funding_arbitrage"][coin] = _to_daily(funding_result.returns)

    # OHLCV cannot validate market-making fills, queue position, adverse selection, or hedging.
    for coin in COINS:
        for regime in ["Overall", *REGIME_ORDER]:
            all_metrics.append(
                {
                    "strategy": "market_making",
                    "coin": coin,
                    "timeframe": "order_book_required",
                    "regime": regime,
                    "status": "not_validated_missing_historical_order_book_and_fills",
                    "periods": 0,
                }
            )

    metrics = pd.DataFrame(all_metrics)
    metrics.to_csv(paths.results / "all_metrics.csv", index=False)
    _write_summaries(paths, metrics, daily_returns)
    _write_status(paths, metrics)
    return metrics


def _run_dca(frame: pd.DataFrame, regimes: pd.Series) -> BacktestResult:
    cash = STARTING_CAPITAL
    shares = 0.0
    equity_values: list[float] = []
    trades: list[dict[str, object]] = []
    last_week: tuple[int, int] | None = None
    for timestamp, row in frame.iterrows():
        week = timestamp.isocalendar()[:2]
        if week != last_week and cash >= 100:
            spend = 100.0
            execution_price = row["open"] * (1 + 0.0005)
            fee = spend * 0.001
            shares_bought = (spend - fee) / execution_price
            shares += shares_bought
            cash -= spend
            trades.append(
                {
                    "entry_time": timestamp,
                    "exit_time": pd.NaT,
                    "side": "long",
                    "entry_price": execution_price,
                    "exit_price": np.nan,
                    "return": np.nan,
                    "pnl": np.nan,
                    "fees_paid": fee,
                    "entry_regime": regimes.reindex(frame.index).loc[timestamp],
                    "bars": np.nan,
                }
            )
        last_week = week
        equity_values.append(cash + shares * row["close"])
    equity = pd.Series(equity_values, index=frame.index)
    returns = equity.pct_change().fillna(0.0)
    result = execute_return_stream(returns, regimes, PERIODS_PER_YEAR["1d"], pd.DataFrame(trades))
    result.equity = equity
    result.position = shares * frame["close"] / equity
    return result


def _run_funding(paths: Paths, coin: str, daily_regimes: pd.DataFrame) -> BacktestResult:
    funding = pd.read_csv(paths.funding / f"{coin}_funding.csv.gz", parse_dates=["timestamp"])
    if funding.empty:
        return execute_return_stream(pd.Series(dtype=float), pd.Series(dtype=str), 365.25 * 3)
    funding["timestamp"] = pd.to_datetime(funding["timestamp"], format="mixed", utc=True)
    funding = funding.set_index("timestamp").sort_index()
    active = funding["funding_rate"].abs() > 0.0005
    # Positive funding: short perp + long spot. Negative funding: long perp + short spot.
    # Delta-neutral price P&L is zero by construction; real funding is retained, while borrow,
    # basis drift and liquidation are explicitly outside this preliminary validation.
    gross = funding["funding_rate"].abs().where(active, 0.0)
    turnover = active.astype(float).diff().abs().fillna(active.astype(float))
    returns = gross - turnover * 2 * ONE_WAY_COST
    known_regimes = regimes_known_at(funding.index, daily_regimes)
    trades = _funding_trade_log(funding, active, known_regimes)
    return execute_return_stream(returns, known_regimes, 365.25 * 3, trades)


def _funding_trade_log(frame: pd.DataFrame, active: pd.Series, regimes: pd.Series) -> pd.DataFrame:
    rows = []
    previous_active = active.shift(1, fill_value=False)
    starts = active & ~previous_active
    ends = ~active & previous_active
    end_times = list(frame.index[ends])
    for start in frame.index[starts]:
        exit_candidates = [value for value in end_times if value > start]
        end = exit_candidates[0] if exit_candidates else frame.index[-1]
        segment = frame.loc[start:end, "funding_rate"]
        pnl_return = float(segment.abs().sum() - 4 * ONE_WAY_COST)
        rows.append(
            {
                "entry_time": start,
                "exit_time": end,
                "side": "delta_neutral",
                "entry_price": frame.loc[start, "mark_price"],
                "exit_price": frame.loc[end, "mark_price"],
                "return": pnl_return,
                "pnl": STARTING_CAPITAL * pnl_return,
                "fees_paid": STARTING_CAPITAL * 4 * ONE_WAY_COST,
                "entry_regime": regimes.loc[start],
                "bars": int(frame.loc[start:end].shape[0]),
            }
        )
    return pd.DataFrame(rows)


def _tag_metrics(
    rows: list[dict[str, object]], strategy: str, coin: str, timeframe: str
) -> list[dict[str, object]]:
    return [{"strategy": strategy, "coin": coin, "timeframe": timeframe, **row} for row in rows]


def _save_result(paths: Paths, strategy: str, coin: str, result: BacktestResult) -> None:
    result.trades.to_csv(
        paths.trades / f"{strategy}_{coin}_trades.csv", index=False, float_format="%.10g"
    )
    returns = pd.DataFrame(
        {"timestamp": result.returns.index, "return": result.returns, "equity": result.equity}
    )
    returns.to_csv(
        paths.returns / f"{strategy}_{coin}_returns.csv.gz",
        index=False,
        compression="gzip",
        float_format="%.10g",
    )
    payload = {row["regime"]: _json_safe(row) for row in result.metrics}
    (paths.metrics / f"{strategy}_{coin}_metrics.json").write_text(
        json.dumps(payload, indent=2, allow_nan=False) + "\n"
    )


def _json_safe(value: object) -> object:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (np.floating, float)) and (pd.isna(value) or np.isinf(value)):
        return None
    if isinstance(value, np.generic):
        return value.item()
    return value


def _to_daily(returns: pd.Series) -> pd.Series:
    return (1 + returns).resample("1D").prod() - 1


def _write_summaries(
    paths: Paths,
    metrics: pd.DataFrame,
    strategy_coin_returns: dict[str, dict[str, pd.Series]],
) -> None:
    completed = metrics[metrics["status"] == "completed_historical_backtest"]
    conditional = completed[completed["regime"].isin(REGIME_ORDER)]
    master = conditional.pivot_table(
        index="strategy", columns="regime", values="sharpe", aggfunc="mean"
    )
    master = master.reindex(columns=REGIME_ORDER)
    master.to_csv(paths.results / "master_summary.csv", float_format="%.6g")

    per_coin = conditional[
        ["coin", "regime", "strategy", "sharpe", "max_drawdown", "total_return"]
    ].copy()
    per_coin["sharpe_rank"] = per_coin.groupby(["coin", "regime"])["sharpe"].rank(
        ascending=False, method="min"
    )
    per_coin.sort_values(["coin", "regime", "sharpe_rank"]).to_csv(
        paths.results / "per_coin_summary.csv", index=False
    )

    portfolio = {}
    for strategy, coin_returns in strategy_coin_returns.items():
        aligned = pd.concat(coin_returns, axis=1).fillna(0.0)
        portfolio[strategy] = aligned.mean(axis=1)
    returns_frame = pd.DataFrame(portfolio).sort_index()
    returns_frame.to_csv(
        paths.results / "strategy_daily_returns.csv", index_label="timestamp", float_format="%.10g"
    )
    returns_frame.corr().to_csv(paths.results / "strategy_correlation.csv", float_format="%.6g")


def _write_status(paths: Paths, metrics: pd.DataFrame) -> None:
    statuses = []
    for strategy, group in metrics.groupby("strategy"):
        complete = bool((group["status"] == "completed_historical_backtest").any())
        statuses.append(
            {
                "strategy": strategy,
                "status": "historical_backtest_completed" if complete else group["status"].iloc[0],
                "validated_coin_count": int(
                    group.loc[group["status"] == "completed_historical_backtest", "coin"].nunique()
                ),
                "evidence": "real Binance candles/funding plus committed trades, returns, and metrics"
                if complete
                else "specification only; historical order-book and fill evidence absent",
                "claim_boundary": "research backtest, not a proven edge or live-trading approval",
            }
        )
    pd.DataFrame(statuses).sort_values("strategy").to_csv(
        paths.results / "validation_status.csv", index=False
    )


def require_inputs(paths: Paths) -> None:
    missing = []
    for coin in COINS:
        for timeframe in ("1d", "4h", "1h"):
            path = paths.raw / f"{coin}_{timeframe}.csv.gz"
            if not path.exists():
                missing.append(path)
        if not (paths.funding / f"{coin}_funding.csv.gz").exists():
            missing.append(paths.funding / f"{coin}_funding.csv.gz")
    if missing:
        raise FileNotFoundError(
            f"Missing {len(missing)} required datasets; run fetch first. First: {missing[0]}"
        )
