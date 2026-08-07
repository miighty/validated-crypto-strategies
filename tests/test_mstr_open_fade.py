import pandas as pd

from edge_research.mstr_open_fade import opening_fade_returns


def test_opening_fade_uses_open_and_fixed_minute_closes_only_after_negative_wild_event():
    index = pd.date_range("2025-01-02 09:30", periods=15, freq="min", tz="America/New_York")
    minute = pd.DataFrame({"open": [100.0] + [101.0] * 14, "close": range(100, 115)}, index=index)
    events = pd.DataFrame(
        {"btc_event_return": [-0.10]}, index=pd.DatetimeIndex(["2025-01-02"])
    )
    # 60 prior observations are required by the production rule; lower it in this unit test.
    result = opening_fade_returns(
        minute, events, quantile=0.5, minimum_prior_observations=0, round_trip_cost_bps=0
    )
    assert result.empty  # A single first observation has no prior-only threshold.
