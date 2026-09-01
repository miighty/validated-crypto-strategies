from __future__ import annotations

"""Daily 20-day-high / 10-day-low breakout continuation (long-only,
single-asset, UNFILTERED) -- dedicated full-validation-ladder study for the
"unconfirmed breakout" control system that appeared as a strong side-result
in both OI-confirmation studies (EXP-2026-09-01-OIBREAKOUT-001 and
EXP-2026-09-01-OITHIN-001) but was never itself the primary hypothesis under
test. Both of those studies' registry notes explicitly flagged this system
as "an untested candidate for a dedicated full-validation-ladder study
(walk-forward/MC/DSR/concentration-fix)".

Genuinely new hypothesis for this repo: this is the FIRST time the plain
20-day-high/10-day-low breakout system itself (no OI filter, no vol-scaling,
no compression filter -- distinct from breakout_compression_validation.py's
4h ATR/Bollinger-width mechanism) is run through the program's full
validation ladder as the primary object of study, rather than as an
incidental baseline inside an OI-filter study.

PRIMARY RULE (frozen before this run inspected any results beyond what was
already visible in the two prior OI studies' baseline numbers):
  1. Entry: daily close > rolling 20-day high computed on the PRIOR 20
     completed daily closes (shift(1), no lookahead -- today's close is
     compared against days t-20..t-1). Enter long at the NEXT daily bar's
     open.
  2. Exit: first daily close that falls below the rolling 10-day low
     computed on the PRIOR 10 completed closes (shift(1), no lookahead).
     Exit at the NEXT daily bar's open. Flat between exit and next
     qualifying entry (non-overlapping trades).
  3. Costs: standard round-trip (2 x ONE_WAY_COST = 30bps) on entry/exit
     notional.
  4. Universe: BTC/ETH/SOL/XRP (matches the two prior OI studies exactly,
     restricted to the OI-study OI-coverage-start window is NOT applied
     here -- full available spot history is used since this study carries
     no OI dependency).

Baselines: cash, buy-and-hold, daily DCA, seeded random-entry-timing control
matching trade count/mean hold.

Validation ladder (per skill's near-miss/DSR discipline):
  - Best-trade-exclusion concentration check (cap 20%).
  - Doubled-cost robustness.
  - 1-bar (1-day) execution-delay robustness (CRITICAL first-pass gate per
    skill's execution-delay-robustness pitfall -- this is a daily-close
    breakout, not a fast oscillator, but still checked).
  - Walk-forward split (first half vs second half of in-sample trades).
  - Monte Carlo return-shuffle permutation test on trade returns (appropriate
    null here: this is a single-asset directional timing rule, not a
    cross-sectional ranking, so time-shuffling trade order/returns is a
    reasonable null for "would randomly-timed trades of this frequency have
    done this well" -- distinct question from the random-timing baseline
    above, which fixes trade count/hold but randomizes ENTRY DATES; this MC
    test instead shuffles the REALIZED RETURN SEQUENCE of the actual trades
    to test whether their favorable ordering/magnitude is distinguishable
    from chance).
  - Deflated Sharpe Ratio at the program's true search-size scale.
"""

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .config import ONE_WAY_COST, Paths, STARTING_CAPITAL
from .data import load_ohlcv

UNIVERSE = ("BTC", "ETH", "SOL", "XRP")
VALIDATION_START = pd.Timestamp("2024-01-01T00:00:00Z")
HOLDOUT_START = pd.Timestamp("2025-01-01T00:00:00Z")

BREAKOUT_LOOKBACK_DAYS = 20
EXIT_LOOKBACK_DAYS = 10
ROUND_TRIP_COST = 2 * ONE_WAY_COST
CONCENTRATION_CAP_PCT = 20.0
RANDOM_SEED = 20260901
MC_TRIALS = 2000
N_STRATEGY_VARIANTS = 96  # program's approximate true search-size proxy as of this run


@dataclass(frozen=True)
class StudyConfig:
    breakout_lookback_days: int = BREAKOUT_LOOKBACK_DAYS
    exit_lookback_days: int = EXIT_LOOKBACK_DAYS
    initial_capital: float = STARTING_CAPITAL
    delay_bars: int = 0
    primary_rule: str = (
        "LONG-ONLY: enter at next daily open when close breaks above the "
        "trailing prior-only 20-day high. Exit at next daily open on the "
        "first close below the trailing prior-only 10-day low. Flat "
        "otherwise, non-overlapping trades. 30bps round-trip cost."
    )


def build_daily_signal(price_1d: pd.DataFrame, config: StudyConfig) -> pd.DataFrame:
    frame = price_1d.reset_index().rename(columns={"index": "timestamp"})
    if "timestamp" not in frame.columns:
        frame = frame.rename(columns={frame.columns[0]: "timestamp"})
    frame = frame.sort_values("timestamp").reset_index(drop=True)

    frame["rolling_high"] = frame["close"].shift(1).rolling(
        config.breakout_lookback_days, min_periods=config.breakout_lookback_days
    ).max()
    frame["rolling_low"] = frame["close"].shift(1).rolling(
        config.exit_lookback_days, min_periods=config.exit_lookback_days
    ).min()
    frame["breakout"] = frame["close"] > frame["rolling_high"]
    frame["exit_break"] = frame["close"] < frame["rolling_low"]
    return frame.set_index("timestamp")


def simulate_long_strategy(
    frame: pd.DataFrame,
    config: StudyConfig,
    entry_column: str = "breakout",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """delay_bars: additional bars of execution lag applied to BOTH entry and
    exit signals (shift(delay_bars) on the boolean trigger series) before
    acting on the next bar's open, per the skill's execution-delay-robustness
    gate."""
    capital = config.initial_capital
    equity_rows = []
    trade_rows = []
    in_position = False
    entry_index = None
    entry_price = None
    entry_time = None
    entry_capital = None

    timestamps = frame.index.to_list()
    opens = frame["open"].to_numpy()
    closes = frame["close"].to_numpy()
    # Signal columns are known only as of THIS bar's close (breakout/exit_break
    # both reference frame["close"].iloc[i]). Execution must therefore happen
    # at the NEXT bar's open at the earliest (i+1), never bar i's own open --
    # using opens[i] would mean trading before the triggering close is even
    # observed (a lookahead bug). config.delay_bars adds ADDITIONAL lag beyond
    # this minimum-realistic 1-bar execution lag (delay_bars=0 -> execute at
    # i+1 open; delay_bars=1 -> execute at i+2 open, etc.).
    raw_entries = frame[entry_column].fillna(False).to_numpy()
    raw_exit_breaks = frame["exit_break"].fillna(False).to_numpy()
    exec_offset = 1 + config.delay_bars

    for i, ts in enumerate(timestamps):
        exec_i = i - exec_offset  # the bar index whose signal is executed at THIS bar's open
        signal_entry = bool(raw_entries[exec_i]) if exec_i >= 0 else False
        signal_exit = bool(raw_exit_breaks[exec_i]) if exec_i >= 0 else False

        if in_position and signal_exit and i > entry_index:
            exit_price = opens[i]
            gross_return = (exit_price - entry_price) / entry_price
            capital *= (1 + gross_return)
            capital *= (1 - ONE_WAY_COST)
            trade_rows.append(
                {
                    "entry_time": entry_time,
                    "exit_time": ts,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "gross_return": gross_return,
                    "capital_at_entry": entry_capital,
                    "capital_at_exit": capital,
                    "trade_return": (capital / entry_capital) - 1.0 if entry_capital else np.nan,
                }
            )
            in_position = False
            entry_index = None
            entry_price = None
            entry_time = None
            entry_capital = None

        if not in_position and signal_entry and i < len(timestamps):
            entry_price = opens[i]
            capital *= (1 - ONE_WAY_COST)
            entry_capital = capital
            entry_index = i
            entry_time = ts
            in_position = True

        equity_rows.append({"timestamp": ts, "capital": capital, "in_position": in_position})

    if in_position:
        exit_price = closes[-1]
        gross_return = (exit_price - entry_price) / entry_price
        capital *= (1 + gross_return)
        capital *= (1 - ONE_WAY_COST)
        trade_rows.append(
            {
                "entry_time": entry_time,
                "exit_time": timestamps[-1],
                "entry_price": entry_price,
                "exit_price": exit_price,
                "gross_return": gross_return,
                "capital_at_entry": entry_capital,
                "capital_at_exit": capital,
                "trade_return": (capital / entry_capital) - 1.0 if entry_capital else np.nan,
                "note": "forced_close_at_sample_end",
            }
        )
        equity_rows[-1]["capital"] = capital

    equity = pd.DataFrame(equity_rows).set_index("timestamp")
    trades = pd.DataFrame(trade_rows)
    return equity, trades


def simulate_buy_and_hold(price: pd.DataFrame, initial_capital: float) -> pd.Series:
    entry_price = float(price["open"].iloc[0]) * (1 + ONE_WAY_COST)
    units = initial_capital / entry_price
    return (units * price["close"]).rename("capital")


def simulate_daily_dca(price: pd.DataFrame, initial_capital: float) -> pd.Series:
    tranche = initial_capital / len(price)
    units = 0.0
    rows = []
    for _, row in price.iterrows():
        execution_price = float(row["open"]) * (1 + ONE_WAY_COST)
        units += tranche / execution_price
        rows.append(units * float(row["close"]))
    return pd.Series(rows, index=price.index, name="capital")


def simulate_random_control(
    frame: pd.DataFrame,
    config: StudyConfig,
    n_trades: int,
    mean_hold_days: int,
    seed: int = RANDOM_SEED,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    n = len(frame)
    hold = max(1, int(round(mean_hold_days)))
    if n_trades == 0 or n < hold + 2:
        return pd.DataFrame(), pd.DataFrame()
    max_start = n - hold - 1
    if max_start <= 0:
        return pd.DataFrame(), pd.DataFrame()
    candidate_starts = rng.choice(
        np.arange(max_start), size=min(n_trades * 5, max_start), replace=False
    )
    candidate_starts.sort()
    chosen = []
    last_end = -10**9
    for s in candidate_starts:
        if s - last_end >= hold:
            chosen.append(s)
            last_end = s + hold
        if len(chosen) >= n_trades:
            break
    entries = np.zeros(n, dtype=bool)
    exit_breaks = np.zeros(n, dtype=bool)
    for s in chosen:
        entries[s] = True
        exit_idx = min(s + hold, n - 1)
        exit_breaks[exit_idx] = True
    fake_frame = frame.copy()
    fake_frame["breakout"] = entries
    fake_frame["exit_break"] = exit_breaks
    fake_config = StudyConfig(delay_bars=0)
    return simulate_long_strategy(fake_frame, fake_config, entry_column="breakout")


def top_trade_pct_of_pnl(trades: pd.DataFrame, initial_capital: float, final_capital: float) -> float | None:
    if trades.empty:
        return None
    total_pnl = final_capital - initial_capital
    if total_pnl == 0:
        return None
    best_idx = trades["trade_return"].abs().idxmax()
    best_pnl = trades.loc[best_idx, "capital_at_exit"] - trades.loc[best_idx, "capital_at_entry"]
    return float(best_pnl / total_pnl) * 100


def simulate_doubled_cost(trades: pd.DataFrame, initial_capital: float) -> float:
    if trades.empty:
        return initial_capital
    extra_cost_factor = (1 - 2 * ONE_WAY_COST)
    capital = initial_capital
    for _, row in trades.iterrows():
        capital *= (1 + row["trade_return"]) * extra_cost_factor
    return capital


def partition_label(ts: pd.Timestamp) -> str:
    if ts < VALIDATION_START:
        return "development_pre_2024"
    if ts < HOLDOUT_START:
        return "validation_2024"
    return "test_2025_onward"


def walk_forward_split(trades: pd.DataFrame) -> dict:
    if trades.empty or len(trades) < 4:
        return {"first_half_sharpe": None, "second_half_sharpe": None, "n_first": 0, "n_second": 0}
    mid = len(trades) // 2
    first = trades.iloc[:mid]["trade_return"].to_numpy()
    second = trades.iloc[mid:]["trade_return"].to_numpy()

    def sharpe(returns: np.ndarray) -> float | None:
        if len(returns) < 2 or returns.std(ddof=1) == 0:
            return None
        return float(returns.mean() / returns.std(ddof=1) * np.sqrt(len(returns)))

    return {
        "first_half_sharpe": sharpe(first),
        "second_half_sharpe": sharpe(second),
        "n_first": len(first),
        "n_second": len(second),
    }


def monte_carlo_permutation(trade_returns: np.ndarray, n_trials: int, seed: int = RANDOM_SEED) -> dict:
    """Shuffle the realized trade-return SEQUENCE (order only, values fixed) and
    also independently resample WITH REPLACEMENT from the pooled return
    distribution to build a null of 'random trades of this magnitude
    distribution' -- reports both since shuffling order alone doesn't change
    mean/std/Sharpe for an i.i.d. statistic (a known degenerate-test pitfall
    for pure reordering). The informative test here is the bootstrap
    resample variant."""
    n = len(trade_returns)
    if n < 2:
        return {"observed_sharpe": None, "p_value": None, "n_trials": n_trials, "note": "insufficient trades"}
    observed_mean = trade_returns.mean()
    observed_std = trade_returns.std(ddof=1)
    if observed_std == 0:
        return {"observed_sharpe": None, "p_value": None, "n_trials": n_trials, "note": "zero variance"}
    observed_sharpe = observed_mean / observed_std * np.sqrt(n)

    rng = np.random.default_rng(seed)
    sim_sharpes = np.empty(n_trials)
    for t in range(n_trials):
        sample = rng.choice(trade_returns, size=n, replace=True)
        s_std = sample.std(ddof=1)
        if s_std == 0:
            sim_sharpes[t] = 0.0
        else:
            sim_sharpes[t] = sample.mean() / s_std * np.sqrt(n)
    # two-sided null centered at zero: what fraction of bootstrap draws from the
    # SAME empirical distribution, shuffled, are >= observed by chance is not
    # meaningful since it's the same data; instead we test against a
    # zero-mean-shifted null (return series demeaned) to ask "is this mean
    # distinguishable from zero given this data's own variance/skew structure".
    demeaned = trade_returns - observed_mean
    null_sharpes = np.empty(n_trials)
    for t in range(n_trials):
        sample = rng.choice(demeaned, size=n, replace=True)
        s_std = sample.std(ddof=1)
        null_sharpes[t] = 0.0 if s_std == 0 else sample.mean() / s_std * np.sqrt(n)
    p_value = float((np.abs(null_sharpes) >= abs(observed_sharpe)).mean())
    return {
        "observed_sharpe": float(observed_sharpe),
        "null_sharpe_std": float(null_sharpes.std()),
        "p_value": p_value,
        "n_trials": n_trials,
    }


def deflated_sharpe_ratio(trade_returns: np.ndarray, bars_per_year: float, n_trials: int) -> dict:
    import math
    n_obs = len(trade_returns)
    if n_obs < 4 or trade_returns.std(ddof=1) == 0:
        return {"dsr_p_value": None, "note": "insufficient trades or zero variance"}
    sr_per_bar = trade_returns.mean() / trade_returns.std(ddof=1)
    sr_annualized = sr_per_bar * np.sqrt(bars_per_year)

    mean_r = trade_returns.mean()
    std_r = trade_returns.std(ddof=1)
    skew = np.mean(((trade_returns - mean_r) / std_r) ** 3)
    kurt = np.mean(((trade_returns - mean_r) / std_r) ** 4)

    se_per_bar = np.sqrt(
        max(1e-12, (1 + 0.5 * sr_per_bar**2 - skew * sr_per_bar + (kurt - 3) / 4 * sr_per_bar**2) / n_obs)
    )

    def norm_ppf(p: float) -> float:
        a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
             1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
        b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
             6.680131188771972e+01, -1.328068155288572e+01]
        c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
             -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
        d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
             3.754408661907416e+00]
        p_low = 0.02425
        p_high = 1 - p_low
        if p <= 0:
            return -np.inf
        if p >= 1:
            return np.inf
        if p < p_low:
            q = math.sqrt(-2 * math.log(p))
            return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                   ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
        elif p <= p_high:
            q = p - 0.5
            r = q * q
            return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
                   (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
        else:
            q = math.sqrt(-2 * math.log(1 - p))
            return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                    ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)

    def norm_cdf(x: float) -> float:
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    if n_trials > 1:
        euler_gamma = 0.5772156649
        expected_max_sr_per_bar = se_per_bar * (
            (1 - euler_gamma) * norm_ppf(1 - 1.0 / n_trials)
            + euler_gamma * norm_ppf(1 - 1.0 / (n_trials * math.e))
        )
    else:
        expected_max_sr_per_bar = 0.0

    dsr_stat = (sr_per_bar - expected_max_sr_per_bar) / se_per_bar
    p_value = 1 - norm_cdf(dsr_stat)

    return {
        "sr_annualized": float(sr_annualized),
        "sr_per_bar": float(sr_per_bar),
        "se_per_bar": float(se_per_bar),
        "n_obs": int(n_obs),
        "n_trials": int(n_trials),
        "dsr_stat": float(dsr_stat),
        "dsr_p_value": float(p_value),
        "passes_at_0.05": bool(p_value < 0.05),
    }


def run_asset_study(paths: Paths, asset: str, config: StudyConfig) -> dict:
    price_1d = load_ohlcv(paths, asset, "1d")
    frame = build_daily_signal(price_1d, config)
    frame["partition"] = [partition_label(ts) for ts in frame.index]

    equity, trades = simulate_long_strategy(frame, config, entry_column="breakout")
    equity["capital"] = equity["capital"].astype(float)

    bh = simulate_buy_and_hold(price_1d, config.initial_capital)
    dca = simulate_daily_dca(price_1d, config.initial_capital)

    delayed_config = StudyConfig(delay_bars=1)
    delayed_equity, delayed_trades = simulate_long_strategy(frame, delayed_config, entry_column="breakout")

    final_capital = float(equity["capital"].iloc[-1])
    delayed_final = float(delayed_equity["capital"].iloc[-1]) if not delayed_equity.empty else config.initial_capital
    doubled_final = simulate_doubled_cost(trades, config.initial_capital)

    if not trades.empty:
        best_idx = trades["trade_return"].abs().idxmax()
        excluded_capital = config.initial_capital
        for i, row in trades.iterrows():
            r = row["trade_return"] if i != best_idx else 0.0
            excluded_capital *= (1 + r)
    else:
        excluded_capital = final_capital
    top_trade_pct = top_trade_pct_of_pnl(trades, config.initial_capital, final_capital)

    mean_hold_days = 5.0
    if not trades.empty:
        holds = [(row["exit_time"] - row["entry_time"]).days for _, row in trades.iterrows()]
        mean_hold_days = float(np.mean(holds)) if holds else 5.0

    random_equity, random_trades = simulate_random_control(frame, config, len(trades), mean_hold_days)

    wf = walk_forward_split(trades)
    mc = monte_carlo_permutation(trades["trade_return"].dropna().to_numpy(), MC_TRIALS) if not trades.empty else {}
    bars_per_year = 365.25 / mean_hold_days if mean_hold_days > 0 else 365.25
    dsr = (
        deflated_sharpe_ratio(trades["trade_return"].dropna().to_numpy(), bars_per_year, N_STRATEGY_VARIANTS)
        if not trades.empty
        else {}
    )

    partition_rows = []
    for label in ("development_pre_2024", "validation_2024", "test_2025_onward"):
        part_trades = (
            trades[trades["entry_time"].apply(lambda t: partition_label(t) == label)]
            if not trades.empty
            else trades
        )
        partition_rows.append(
            {
                "asset": asset,
                "partition": label,
                "n_trades": len(part_trades),
                "mean_trade_return_pct": (
                    float(part_trades["trade_return"].mean() * 100) if len(part_trades) else np.nan
                ),
            }
        )

    return {
        "asset": asset,
        "frame": frame,
        "equity": equity,
        "trades": trades,
        "bh": bh,
        "dca": dca,
        "delayed_final": delayed_final,
        "delayed_n_trades": len(delayed_trades),
        "doubled_final": doubled_final,
        "excluded_capital": excluded_capital,
        "top_trade_pct": top_trade_pct,
        "random_equity": random_equity,
        "random_trades": random_trades,
        "partition_rows": partition_rows,
        "mean_hold_days": mean_hold_days,
        "walk_forward": wf,
        "monte_carlo": mc,
        "dsr": dsr,
    }


def classify_verdict(result: dict, initial_capital: float) -> tuple[str, dict]:
    primary_final = float(result["equity"]["capital"].iloc[-1])
    bh_final = float(result["bh"].iloc[-1])
    dca_final = float(result["dca"].iloc[-1])
    random_final = (
        float(result["random_equity"]["capital"].iloc[-1])
        if not result["random_equity"].empty
        else initial_capital
    )
    doubled_final = result["doubled_final"]
    delayed_final = result["delayed_final"]

    test_trades = [r for r in result["partition_rows"] if r["partition"] == "test_2025_onward"]
    has_holdout_trades = bool(test_trades and test_trades[0]["n_trades"] > 0)

    beats_cash = primary_final > initial_capital
    beats_bh = primary_final > bh_final
    beats_dca = primary_final > dca_final
    beats_random = primary_final > random_final
    survives_doubled_cost = doubled_final > initial_capital
    survives_exclusion = result["excluded_capital"] > initial_capital
    survives_delay = delayed_final > initial_capital
    concentration_ok = (
        result["top_trade_pct"] is None or abs(result["top_trade_pct"]) < CONCENTRATION_CAP_PCT
    )
    dsr_passes = bool(result["dsr"].get("passes_at_0.05")) if result["dsr"] else False
    mc_significant = bool(
        result["monte_carlo"].get("p_value") is not None and result["monte_carlo"]["p_value"] < 0.05
    )

    gates = {
        "beats_cash": beats_cash,
        "beats_bh": beats_bh,
        "beats_dca": beats_dca,
        "beats_random_control": beats_random,
        "survives_doubled_cost": survives_doubled_cost,
        "survives_best_trade_exclusion": survives_exclusion,
        "survives_1bar_delay": survives_delay,
        "concentration_ok": concentration_ok,
        "has_holdout_trades": has_holdout_trades,
        "monte_carlo_significant": mc_significant,
        "deflated_sharpe_passes": dsr_passes,
    }
    verdict = "CANDIDATE" if all(gates.values()) else "REJECTED"
    return verdict, gates


def dataframe_to_markdown(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_(no rows)_\n"
    formatted = frame.copy()
    for col in formatted.columns:
        if pd.api.types.is_float_dtype(formatted[col]):
            formatted[col] = formatted[col].map(lambda v: f"{v:.4f}" if pd.notna(v) else "")
    header = "| " + " | ".join(str(c) for c in formatted.columns) + " |"
    sep = "| " + " | ".join("---" for _ in formatted.columns) + " |"
    body_lines = [
        "| " + " | ".join(str(v) for v in row) + " |" for row in formatted.itertuples(index=False)
    ]
    return "\n".join([header, sep, *body_lines])


def write_report(output: Path, all_results: dict, config: StudyConfig) -> None:
    lines = ["# Plain Daily 20-Day-High / 10-Day-Low Breakout Continuation -- Full Validation", ""]
    lines.append("## Primary rule")
    lines.append(f"> {config.primary_rule}")
    lines.append("")
    lines.append("## Data sources")
    lines.append("- Real Binance spot 1d OHLCV (already cached, `data/raw/*_1d.csv.gz`). No OI dependency, no synthetic data.")
    lines.append("")
    lines.append("## Per-asset results")
    verdicts = {}
    for asset, result in all_results.items():
        lines.append(f"### {asset}")
        lines.append(f"- Trades: **{len(result['trades'])}** (mean hold {result['mean_hold_days']:.1f}d)")
        primary_final = float(result["equity"]["capital"].iloc[-1])
        bh_final = float(result["bh"].iloc[-1])
        dca_final = float(result["dca"].iloc[-1])
        random_final = (
            float(result["random_equity"]["capital"].iloc[-1])
            if not result["random_equity"].empty
            else config.initial_capital
        )
        lines.append(f"- Primary final capital: **${primary_final:,.2f}** (start ${config.initial_capital:,.0f})")
        lines.append(f"- Buy-and-hold final: **${bh_final:,.2f}**")
        lines.append(f"- Daily DCA final: **${dca_final:,.2f}**")
        lines.append(f"- Seeded random-timing control final: **${random_final:,.2f}** ({len(result['random_trades'])} trades)")
        lines.append(f"- Doubled-cost final: **${result['doubled_final']:,.2f}**")
        lines.append(f"- 1-bar delayed-execution final: **${result['delayed_final']:,.2f}** ({result['delayed_n_trades']} trades)")
        lines.append(f"- Best-trade-exclusion final: **${result['excluded_capital']:,.2f}**")
        lines.append(f"- Top single-trade % of total PnL: **{result['top_trade_pct']}**")
        lines.append(f"- Walk-forward split: {result['walk_forward']}")
        lines.append(f"- Monte Carlo bootstrap-null test: {result['monte_carlo']}")
        lines.append(f"- Deflated Sharpe (n_trials={N_STRATEGY_VARIANTS}): {result['dsr']}")
        verdict, gates = classify_verdict(result, config.initial_capital)
        verdicts[asset] = verdict
        lines.append(f"- Gates: {gates}")
        lines.append(f"- Verdict: **{verdict}**")
        lines.append("")
        lines.append("Partition breakdown:")
        lines.append(dataframe_to_markdown(pd.DataFrame(result["partition_rows"])))
        lines.append("")
    lines.append("## Overall verdict")
    n_candidate = sum(1 for v in verdicts.values() if v == "CANDIDATE")
    lines.append(f"{n_candidate}/{len(verdicts)} assets cleared every gate.")
    if n_candidate == 0:
        lines.append("\n**REJECTED** -- no asset cleared every gate.")
    elif n_candidate == len(verdicts):
        lines.append("\n**CANDIDATE** -- every asset cleared every gate, including Deflated Sharpe and Monte Carlo significance.")
    else:
        lines.append(f"\n**MIXED** -- {n_candidate}/{len(verdicts)} assets cleared every gate.")
    output.write_text("\n".join(lines))


def main() -> None:
    paths = Paths(root=Path(__file__).resolve().parents[2])
    config = StudyConfig()
    all_results = {}
    for asset in UNIVERSE:
        all_results[asset] = run_asset_study(paths, asset, config)

    ts = pd.Timestamp.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out_dir = paths.results / "breakout_daily_20high" / "runs" / f"run-{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    combined_trades = []
    for asset, result in all_results.items():
        t = result["trades"].copy()
        t["asset"] = asset
        combined_trades.append(t)
        verdict, gates = classify_verdict(result, config.initial_capital)
        with open(out_dir / f"{asset}_gates.json", "w") as f:
            json.dump({"verdict": verdict, "gates": gates}, f, indent=2, default=str)
    pd.concat(combined_trades, ignore_index=True).to_csv(out_dir / "trades.csv", index=False)

    write_report(out_dir / "REPORT.md", all_results, config)
    print(f"Report written to {out_dir / 'REPORT.md'}")


if __name__ == "__main__":
    main()
