from __future__ import annotations

import numpy as np
import pandas as pd

from .config import COINS, Paths
from .data import load_ohlcv
from .indicators import feature_frame

REGIME_ORDER = [
    "Crash/Capitulation",
    "High Vol Expansion",
    "Bull Trend",
    "Bear Trend",
    "Range/Chop",
]


def classify(frame: pd.DataFrame) -> pd.DataFrame:
    out = feature_frame(frame)
    out["drawdown_30"] = out["close"] / out["high"].rolling(30).max() - 1
    out["atr60_mean"] = out["atr14"].rolling(60).mean()
    out["bb_width20_median"] = out["bb_width"].rolling(20).median()
    out["volume20_mean"] = out["volume"].rolling(20).mean()

    crash = (out["drawdown_30"] < -0.25) & (out["volume"] > 2 * out["volume20_mean"])
    high_vol = out["atr14"] > 2 * out["atr60_mean"]
    bull = (out["adx"] > 25) & (out["plus_di"] > out["minus_di"]) & (out["close"] > out["sma50"])
    bear = (out["adx"] > 25) & (out["minus_di"] > out["plus_di"]) & (out["close"] < out["sma50"])
    explicit_range = (out["adx"] < 20) & (out["bb_width"] < out["bb_width20_median"])

    # Priority is exact. Range/Chop is also the disclosed residual class so every finalized
    # day receives one of the five requested labels; range_rule_matched preserves the distinction.
    out["regime"] = np.select(
        [crash, high_vol, bull, bear],
        REGIME_ORDER[:4],
        default="Range/Chop",
    )
    out["range_rule_matched"] = explicit_range
    out["warmup_complete"] = (
        out[["adx", "atr60_mean", "sma50", "bb_width20_median"]].notna().all(axis=1)
    )
    return out


def generate(paths: Paths) -> dict[str, pd.DataFrame]:
    generated: dict[str, pd.DataFrame] = {}
    for coin in COINS:
        daily = load_ohlcv(paths, coin, "1d")
        regimes = classify(daily)
        destination = paths.regimes / f"{coin}_regimes.csv"
        if not destination.exists():
            regimes.reset_index().to_csv(destination, index=False, float_format="%.10g")
        generated[coin] = regimes
        counts = regimes.loc[regimes["warmup_complete"], "regime"].value_counts(normalize=True)
        print(
            f"Regimes {coin}: "
            + ", ".join(f"{name}={counts.get(name, 0):.1%}" for name in REGIME_ORDER)
        )
    return generated


def load_regimes(paths: Paths, coin: str) -> pd.DataFrame:
    frame = pd.read_csv(paths.regimes / f"{coin}_regimes.csv", parse_dates=["timestamp"])
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    return frame.set_index("timestamp").sort_index()


def regimes_known_at(index: pd.DatetimeIndex, daily: pd.DataFrame) -> pd.Series:
    # A regime computed from a daily candle becomes knowable only after that candle closes.
    availability = pd.DataFrame(
        {
            "available_at": pd.to_datetime(daily.index.asi8 + 86_400_000_000_000, utc=True),
            "regime": daily["regime"].to_numpy(),
        }
    ).sort_values("available_at")
    query = pd.DataFrame({"timestamp": pd.DatetimeIndex(index)}).sort_values("timestamp")
    merged = pd.merge_asof(
        query,
        availability,
        left_on="timestamp",
        right_on="available_at",
        direction="backward",
    )
    return pd.Series(merged["regime"].fillna("Unavailable").to_numpy(), index=query["timestamp"])
