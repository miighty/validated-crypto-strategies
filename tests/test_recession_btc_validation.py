import pandas as pd

from crypto_regime_backtest.recession_btc_validation import StrategySpec, build_signal_panel, classify_verdict


def test_build_signal_panel_applies_cooldown_and_requires_price_window() -> None:
    timestamps = pd.date_range("2026-01-01", periods=240, freq="h", tz="UTC")
    hourly = pd.DataFrame(
        {
            "timestamp": timestamps,
            "yes_price": [0.50] * 240,
            "trade_count": [1.0] * 240,
            "traded_notional": [100.0] * 240,
            "slug": ["us-recession-by-end-of-2026"] * 240,
        }
    )
    hourly.loc[24, "yes_price"] = 0.44
    hourly.loc[130, "yes_price"] = 0.39
    hourly.loc[220, "yes_price"] = 0.35
    spec = StrategySpec(name="test", lookback_hours=24, delta_threshold=0.05, level_threshold=0.45, hold_hours=72)

    signals = build_signal_panel(hourly, pd.Index(timestamps), spec)

    assert list(signals["entry_time"]) == [timestamps[25], timestamps[131]]
    assert list(signals["exit_time"]) == [timestamps[97], timestamps[203]]
    assert list(signals["asset"]) == ["BTC", "BTC"]


class _Result:
    def __init__(self, strategy: str, terminal_value: float) -> None:
        self.summary = {"strategy": strategy, "terminal_value": terminal_value}


def test_classify_verdict_rejects_when_btc_dca_wins() -> None:
    primary = {"event_count": 8, "holdout_trade_count": 3, "terminal_value": 9800.0}
    daily = [_Result("daily_btc_dca", 10_100.0)]
    hostile = pd.DataFrame(
        [
            {"check": "always_long_same_schedule", "beats_primary": False},
            {"check": "random_asset_schedule", "beats_primary": False},
        ]
    )
    sensitivity = pd.DataFrame(
        [
            {"delta_threshold": 0.05, "level_threshold": 0.45, "hold_hours": 72, "terminal_value": 9800.0},
        ]
    )

    verdict, reason = classify_verdict(primary, daily, hostile, sensitivity)

    assert verdict == "Rejected"
    assert "BTC DCA" in reason
