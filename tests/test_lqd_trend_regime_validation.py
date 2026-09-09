from __future__ import annotations

import pandas as pd

from crypto_regime_backtest import lqd_trend_regime_validation as lqd


def test_build_state_uses_prior_only_sma_and_one_day_action_lag() -> None:
    dates = pd.date_range("2020-01-01", periods=205, freq="D", tz="UTC")
    values = [100.0] * 200 + [101.0, 102.0, 90.0, 110.0, 111.0]
    df = pd.DataFrame({"date": dates, "lqd": values})

    state = lqd.build_state(df)
    first_signal_day = pd.Timestamp("2020-07-19", tz="UTC")

    assert state.loc[first_signal_day, "sma200_prior"] == 100.0
    assert bool(state.loc[first_signal_day, "risk_on_signal_close"]) is True
    assert bool(state.loc[first_signal_day, "risk_on_actionable"]) is False
    assert bool(state.loc[pd.Timestamp("2020-07-20", tz="UTC"), "risk_on_actionable"]) is True


def test_simulate_enters_and_exits_on_lqd_allowed_state() -> None:
    idx = pd.date_range("2024-01-01", periods=4, freq="D", tz="UTC")
    spot = pd.DataFrame({"open": [100.0, 110.0, 120.0, 130.0], "close": [110.0, 120.0, 130.0, 140.0]}, index=idx)
    allowed = pd.Series([True, True, False, True], index=idx)

    eq, trades = lqd.simulate(spot, allowed, 0.0)

    assert len(trades) == 2
    assert trades.iloc[0]["entry_time"] == idx[0]
    assert trades.iloc[0]["exit_time"] == idx[2]
    assert eq["equity"].iloc[-1] > 10_000.0
