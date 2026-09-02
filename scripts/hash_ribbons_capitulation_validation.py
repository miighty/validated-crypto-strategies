"""EXP-2026-09-02-HASHRIBBONS-001: Bitcoin Hash Ribbons miner-capitulation-recovery
signal, tested on real spot BTC/USDT data.

Hypothesis (preregistered, frozen before any result inspected):
  The classic "Hash Ribbons" indicator (Charles Edwards / Capriole Investments)
  tracks BTC network hashrate 30d SMA vs 60d SMA. When the 30d SMA crosses BELOW
  the 60d SMA, unprofitable miners are capitulating (shutting down rigs) --
  historically a period of maximum seller exhaustion/fear. When the 30d SMA
  crosses back ABOVE the 60d SMA ("recovery"), surviving miners are back to
  profitability and forced-selling pressure has ended -- the classic buy signal.
  This is a genuinely new data source for this repo (real Blockchain.com public
  network hashrate API, first use here -- entirely independent of every prior
  Binance/Hyperliquid/Bybit perp funding/OI/CFTC-COT positioning study) and a
  genuinely new mechanism (miner economics / production-cost capitulation,
  distinct from every prior sentiment-index, calendar, trend, or positioning
  signal tested in this program).

PRIMARY RULE (frozen before this run inspected any results):
  1. Compute BTC network hashrate 30-day SMA and 60-day SMA (shift(1), no
     lookahead -- signal known only as of the PRIOR completed day).
  2. "Capitulation" state = 30d SMA < 60d SMA. "Recovery" signal fires on the
     first day the 30d SMA crosses back ABOVE the 60d SMA after having been
     below it (a discrete cross-up event, not a continuous regime state).
  3. Entry: buy spot BTC at the NEXT daily bar's open following a recovery
     cross-up signal.
  4. Exit: hold a FIXED 90-day horizon (this is a slow-moving structural signal;
     the classic Hash Ribbons thesis is a multi-month accumulation-zone call,
     not a short-horizon trade), exit at the next daily bar's open after the
     90-day holding period elapses. Non-overlapping: while in a position, new
     recovery signals are ignored (only one open trade at a time).
  5. Costs: repo-standard 30bps round-trip (15bps one-way fee+slippage).
  6. Universe: BTC ONLY -- hashrate is a Bitcoin-specific security-budget
     mechanism; there is no equivalent real hashrate metric for ETH/SOL/XRP in
     this repo (Ethereum moved to PoS in 2022, has no hashrate; SOL/XRP are
     not PoW). No proxy fabricated for the other three assets -- this is
     necessarily and honestly a 1-asset study, like the Deribit DVOL study
     was necessarily BTC/ETH-only.

Baselines: cash, BTC buy-and-hold, BTC daily DCA, seeded random-entry-timing
control matching trade count and fixed 90-day hold.

Validation ladder (per skill discipline):
  - Best-trade-exclusion concentration check (cap 20%).
  - Doubled-cost robustness.
  - 1-day execution-delay robustness.
  - Chronological partition check: development (pre-2021), validation
    (2021-2023), test/holdout (2024 onward) -- real holdout trades required.
  - Walk-forward split (first half vs second half of in-sample trades).
  - Monte Carlo bootstrap-resample significance test on trade returns.
  - Deflated Sharpe Ratio at the program's true search-size scale.

Fastest rejection criterion (preregistered): if the strategy does not beat
BTC buy-and-hold AND BTC daily DCA after costs, OR has zero holdout trades,
OR fails the concentration cap, it is REJECTED regardless of other checks.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crypto_regime_backtest.config import Paths, project_root, FEE_RATE, SLIPPAGE_RATE

ROOT = project_root()
PATHS = Paths(ROOT)
ONE_WAY_COST = FEE_RATE + SLIPPAGE_RATE
ROUND_TRIP_COST = 2 * ONE_WAY_COST
INITIAL_CAPITAL = 10_000.0

FAST_WINDOW = 30
SLOW_WINDOW = 60
HOLD_DAYS = 90
RANDOM_SEED = 20260902
MC_TRIALS = 5000
CONCENTRATION_CAP_PCT = 20.0
# Program's approximate true search-size proxy as of this run (see
# breakout_daily_20high_validation.py's N_STRATEGY_VARIANTS=96 as of 2026-09-01;
# this study is variant #97+ counting the toptrader/retail-ratio studies since).
N_STRATEGY_VARIANTS = 100

VALIDATION_START = pd.Timestamp("2021-01-01T00:00:00Z")
HOLDOUT_START = pd.Timestamp("2024-01-01T00:00:00Z")


def load_hashrate() -> pd.DataFrame:
    path = ROOT / "data" / "hashrate" / "btc_hashrate_1d.csv.gz"
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.drop_duplicates("timestamp").sort_values("timestamp").set_index("timestamp")
    return df


def load_btc_daily() -> pd.DataFrame:
    path = PATHS.raw / "BTC_1d.csv.gz"
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df.set_index("timestamp").sort_index()


def build_signal(hashrate: pd.DataFrame, price: pd.DataFrame) -> pd.DataFrame:
    frame = price.join(hashrate, how="left")
    frame["hashrate"] = frame["hashrate"].ffill()
    frame["sma_fast"] = frame["hashrate"].rolling(FAST_WINDOW, min_periods=FAST_WINDOW).mean()
    frame["sma_slow"] = frame["hashrate"].rolling(SLOW_WINDOW, min_periods=SLOW_WINDOW).mean()
    # Shift by 1: signal known only as of prior day's close (no lookahead).
    fast_prior = frame["sma_fast"].shift(1)
    slow_prior = frame["sma_slow"].shift(1)
    below = fast_prior < slow_prior
    above = fast_prior >= slow_prior
    was_below_yesterday = below.shift(1).fillna(False)
    frame["recovery_signal"] = was_below_yesterday & above
    frame["capitulation_state"] = below
    return frame


def simulate_strategy(frame: pd.DataFrame, delay_bars: int = 0) -> tuple[pd.DataFrame, pd.DataFrame]:
    timestamps = frame.index.to_list()
    opens = frame["open"].to_numpy()
    closes = frame["close"].to_numpy()
    raw_signal = frame["recovery_signal"].fillna(False).to_numpy()
    n = len(frame)
    exec_offset = 1 + delay_bars  # signal known at close of day i; execute at open of i+1+delay

    capital = INITIAL_CAPITAL
    in_position = False
    entry_price = None
    entry_time = None
    entry_capital = None
    hold_until_idx = None
    equity_rows = []
    trade_rows = []

    for i, ts in enumerate(timestamps):
        sig_i = i - exec_offset
        signal_entry = bool(raw_signal[sig_i]) if sig_i >= 0 else False

        if in_position and i >= hold_until_idx:
            exit_price = opens[i]
            gross_return = (exit_price - entry_price) / entry_price
            capital *= (1 + gross_return)
            capital *= (1 - ONE_WAY_COST)
            trade_rows.append({
                "entry_time": entry_time, "exit_time": ts,
                "entry_price": entry_price, "exit_price": exit_price,
                "gross_return": gross_return,
                "capital_at_entry": entry_capital, "capital_at_exit": capital,
                "trade_return": (capital / entry_capital) - 1.0 if entry_capital else np.nan,
            })
            in_position = False
            entry_price = None
            entry_time = None
            entry_capital = None
            hold_until_idx = None

        if not in_position and signal_entry:
            entry_price = opens[i]
            capital *= (1 - ONE_WAY_COST)
            entry_capital = capital
            entry_time = ts
            in_position = True
            hold_until_idx = min(i + HOLD_DAYS, n - 1)

        equity_rows.append({"timestamp": ts, "capital": capital, "in_position": in_position})

    if in_position:
        exit_price = closes[-1]
        gross_return = (exit_price - entry_price) / entry_price
        capital *= (1 + gross_return)
        capital *= (1 - ONE_WAY_COST)
        trade_rows.append({
            "entry_time": entry_time, "exit_time": timestamps[-1],
            "entry_price": entry_price, "exit_price": exit_price,
            "gross_return": gross_return,
            "capital_at_entry": entry_capital, "capital_at_exit": capital,
            "trade_return": (capital / entry_capital) - 1.0 if entry_capital else np.nan,
            "note": "forced_close_at_sample_end",
        })
        equity_rows[-1]["capital"] = capital

    equity = pd.DataFrame(equity_rows).set_index("timestamp")
    trades = pd.DataFrame(trade_rows)
    return equity, trades


def simulate_buy_and_hold(price: pd.DataFrame) -> pd.Series:
    entry_price = float(price["open"].iloc[0]) * (1 + ONE_WAY_COST)
    units = INITIAL_CAPITAL / entry_price
    return (units * price["close"]).rename("capital")


def simulate_daily_dca(price: pd.DataFrame) -> pd.Series:
    tranche = INITIAL_CAPITAL / len(price)
    units = 0.0
    rows = []
    for _, row in price.iterrows():
        execution_price = float(row["open"]) * (1 + ONE_WAY_COST)
        units += tranche / execution_price
        rows.append(units * float(row["close"]))
    return pd.Series(rows, index=price.index, name="capital")


def simulate_random_control(frame: pd.DataFrame, n_trades: int, seed: int = RANDOM_SEED) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    n = len(frame)
    hold = HOLD_DAYS
    if n_trades == 0 or n < hold + 2:
        return pd.DataFrame(), pd.DataFrame()
    max_start = n - hold - 1
    if max_start <= 0:
        return pd.DataFrame(), pd.DataFrame()
    candidate_starts = rng.choice(np.arange(max_start), size=min(n_trades * 5, max_start), replace=False)
    candidate_starts.sort()
    chosen = []
    last_end = -10**9
    for s in candidate_starts:
        if s - last_end >= hold:
            chosen.append(s)
            last_end = s + hold
        if len(chosen) >= n_trades:
            break
    fake_signal = np.zeros(n, dtype=bool)
    for s in chosen:
        fake_signal[s] = True
    fake_frame = frame.copy()
    # shift so that exec_offset=1 lands the fake entry exactly at s+1
    fake_frame["recovery_signal"] = pd.Series(fake_signal, index=frame.index).shift(-1).fillna(False)
    return simulate_strategy(fake_frame, delay_bars=0)


def top_trade_pct_of_pnl(trades: pd.DataFrame, final_capital: float) -> float | None:
    if trades.empty:
        return None
    total_pnl = final_capital - INITIAL_CAPITAL
    if total_pnl == 0:
        return None
    best_idx = trades["trade_return"].abs().idxmax()
    best_pnl = trades.loc[best_idx, "capital_at_exit"] - trades.loc[best_idx, "capital_at_entry"]
    return float(best_pnl / total_pnl) * 100


def simulate_doubled_cost(trades: pd.DataFrame) -> float:
    if trades.empty:
        return INITIAL_CAPITAL
    extra_cost_factor = (1 - 2 * ONE_WAY_COST)
    capital = INITIAL_CAPITAL
    for _, row in trades.iterrows():
        capital *= (1 + row["trade_return"]) * extra_cost_factor
    return capital


def best_trade_excluded(trades: pd.DataFrame) -> float:
    if trades.empty:
        return INITIAL_CAPITAL
    best_idx = trades["trade_return"].abs().idxmax()
    capital = INITIAL_CAPITAL
    for i, row in trades.iterrows():
        r = row["trade_return"] if i != best_idx else 0.0
        capital *= (1 + r)
    return capital


def partition_label(ts: pd.Timestamp) -> str:
    if ts < VALIDATION_START:
        return "development_pre_2021"
    if ts < HOLDOUT_START:
        return "validation_2021_2023"
    return "test_2024_onward"


def walk_forward_split(trades: pd.DataFrame) -> dict:
    if trades.empty or len(trades) < 4:
        return {"first_half_sharpe": None, "second_half_sharpe": None, "n_first": 0, "n_second": 0}
    mid = len(trades) // 2
    first = trades.iloc[:mid]["trade_return"].to_numpy()
    second = trades.iloc[mid:]["trade_return"].to_numpy()

    def sharpe(returns):
        if len(returns) < 2 or returns.std(ddof=1) == 0:
            return None
        return float(returns.mean() / returns.std(ddof=1) * np.sqrt(len(returns)))

    return {
        "first_half_sharpe": sharpe(first), "second_half_sharpe": sharpe(second),
        "n_first": len(first), "n_second": len(second),
    }


def monte_carlo_bootstrap(trade_returns: np.ndarray, n_trials: int, seed: int = RANDOM_SEED) -> dict:
    n = len(trade_returns)
    if n < 2:
        return {"observed_sharpe": None, "p_value": None, "n_trials": n_trials, "note": "insufficient trades"}
    observed_mean = trade_returns.mean()
    observed_std = trade_returns.std(ddof=1)
    if observed_std == 0:
        return {"observed_sharpe": None, "p_value": None, "n_trials": n_trials, "note": "zero variance"}
    observed_sharpe = observed_mean / observed_std * np.sqrt(n)

    rng = np.random.default_rng(seed)
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
        "p_value": p_value, "n_trials": n_trials,
    }


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


def deflated_sharpe_ratio(trade_returns: np.ndarray, bars_per_year: float, n_trials: int) -> dict:
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
        "sr_annualized": float(sr_annualized), "sr_per_bar": float(sr_per_bar),
        "se_per_bar": float(se_per_bar), "n_obs": int(n_obs), "n_trials": int(n_trials),
        "dsr_stat": float(dsr_stat), "dsr_p_value": float(p_value),
        "passes_at_0.05": bool(p_value < 0.05),
    }


def main() -> None:
    hashrate = load_hashrate()
    price = load_btc_daily()
    frame = build_signal(hashrate, price)
    frame["partition"] = [partition_label(ts) for ts in frame.index]

    n_recovery_signals = int(frame["recovery_signal"].sum())
    n_capitulation_days = int(frame["capitulation_state"].sum())
    print(f"Data: {len(frame)} daily rows, {frame.index.min()} -> {frame.index.max()}")
    print(f"Capitulation days (30d SMA < 60d SMA): {n_capitulation_days} ({n_capitulation_days/len(frame)*100:.1f}%)")
    print(f"Recovery cross-up signals fired: {n_recovery_signals}")

    equity, trades = simulate_strategy(frame, delay_bars=0)
    final_capital = float(equity["capital"].iloc[-1])

    delayed_equity, delayed_trades = simulate_strategy(frame, delay_bars=1)
    delayed_final = float(delayed_equity["capital"].iloc[-1]) if not delayed_equity.empty else INITIAL_CAPITAL

    doubled_final = simulate_doubled_cost(trades)
    excluded_final = best_trade_excluded(trades)
    top_trade_pct = top_trade_pct_of_pnl(trades, final_capital)

    bh = simulate_buy_and_hold(price)
    dca = simulate_daily_dca(price)
    bh_final = float(bh.iloc[-1])
    dca_final = float(dca.iloc[-1])

    random_equity, random_trades = simulate_random_control(frame, len(trades))
    random_final = float(random_equity["capital"].iloc[-1]) if not random_equity.empty else INITIAL_CAPITAL

    wf = walk_forward_split(trades)
    mc = monte_carlo_bootstrap(trades["trade_return"].dropna().to_numpy(), MC_TRIALS) if not trades.empty else {}
    bars_per_year = 365.25 / HOLD_DAYS
    dsr = (
        deflated_sharpe_ratio(trades["trade_return"].dropna().to_numpy(), bars_per_year, N_STRATEGY_VARIANTS)
        if not trades.empty else {}
    )

    partition_rows = []
    for label in ("development_pre_2021", "validation_2021_2023", "test_2024_onward"):
        if not trades.empty:
            part_trades = trades[trades["entry_time"].apply(lambda t: partition_label(t) == label)]
        else:
            part_trades = trades
        partition_rows.append({
            "partition": label, "n_trades": len(part_trades),
            "mean_trade_return_pct": (float(part_trades["trade_return"].mean() * 100) if len(part_trades) else np.nan),
        })
    partition_df = pd.DataFrame(partition_rows)

    n_holdout_trades = int(partition_df.loc[partition_df["partition"] == "test_2024_onward", "n_trades"].iloc[0])

    out_dir = ROOT / "results" / "hash_ribbons_capitulation" / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts_str = pd.Timestamp.utcnow().strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_dir / f"run-{ts_str}"
    run_dir.mkdir(parents=True, exist_ok=True)

    trades.to_csv(run_dir / "trades.csv", index=False)
    equity.to_csv(run_dir / "equity.csv")
    partition_df.to_csv(run_dir / "partition_summary.csv", index=False)

    summary_rows = [
        {"strategy": "Hash Ribbons recovery (primary)", "final_capital": final_capital, "n_trades": len(trades)},
        {"strategy": "BTC buy-and-hold", "final_capital": bh_final, "n_trades": 1},
        {"strategy": "BTC daily DCA", "final_capital": dca_final, "n_trades": len(price)},
        {"strategy": "Seeded random-timing control", "final_capital": random_final, "n_trades": len(random_trades)},
        {"strategy": "Doubled-cost primary", "final_capital": doubled_final, "n_trades": len(trades)},
        {"strategy": "Best-trade-excluded primary", "final_capital": excluded_final, "n_trades": max(len(trades) - 1, 0)},
        {"strategy": "1-day execution-delay primary", "final_capital": delayed_final, "n_trades": len(delayed_trades)},
    ]
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(run_dir / "strategy_summary.csv", index=False)

    beats_bh = final_capital > bh_final
    beats_dca = final_capital > dca_final
    beats_random = final_capital > random_final
    survives_doubled_cost = doubled_final > INITIAL_CAPITAL
    concentration_ok = (top_trade_pct is None) or (abs(top_trade_pct) <= CONCENTRATION_CAP_PCT)
    has_holdout_trades = n_holdout_trades > 0

    verdict = "CANDIDATE" if (beats_bh and beats_dca and beats_random and concentration_ok and has_holdout_trades) else "REJECTED"

    print("\n" + summary_df.to_string(index=False))
    print(f"\nTop-trade PnL share: {top_trade_pct}")
    print(f"Concentration OK (<=20%): {concentration_ok}")
    print(f"Holdout (2024+) trades: {n_holdout_trades}")
    print(f"Walk-forward: {wf}")
    print(f"Monte Carlo bootstrap: {mc}")
    print(f"Deflated Sharpe: {dsr}")
    print(f"\nBeats BH: {beats_bh}, Beats DCA: {beats_dca}, Beats random: {beats_random}")
    print(f"Verdict: {verdict}")

    verdict_path = run_dir / "verdict.txt"
    with open(verdict_path, "w") as f:
        f.write(f"final_capital={final_capital}\n")
        f.write(f"bh_final={bh_final}\ndca_final={dca_final}\nrandom_final={random_final}\n")
        f.write(f"doubled_final={doubled_final}\nexcluded_final={excluded_final}\ndelayed_final={delayed_final}\n")
        f.write(f"top_trade_pct={top_trade_pct}\nconcentration_ok={concentration_ok}\n")
        f.write(f"n_trades={len(trades)}\nn_holdout_trades={n_holdout_trades}\n")
        f.write(f"beats_bh={beats_bh}\nbeats_dca={beats_dca}\nbeats_random={beats_random}\n")
        f.write(f"walk_forward={wf}\n")
        f.write(f"monte_carlo={mc}\n")
        f.write(f"deflated_sharpe={dsr}\n")
        f.write(f"verdict={verdict}\n")

    print(f"\nArtifacts written to {run_dir}")


if __name__ == "__main__":
    main()
