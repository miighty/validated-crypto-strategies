import pandas as pd

from crypto_regime_backtest.alt_etf_btc_panel_validation import StrategySpec, build_alt_etf_signals


def test_build_alt_etf_signals_pools_assets_and_uses_next_open_entry():
    timestamps = pd.date_range("2025-01-01", periods=30, freq="h", tz="UTC")
    hourly = pd.concat(
        [
            pd.DataFrame(
                {
                    "timestamp": timestamps,
                    "family": "eth_etf",
                    "slug": "eth-market",
                    "question": "ETH ETF?",
                    "yes_price": [0.40] * 24 + [0.56, 0.57, 0.58, 0.59, 0.60, 0.61],
                }
            ),
            pd.DataFrame(
                {
                    "timestamp": timestamps,
                    "family": "sol_etf",
                    "slug": "sol-market",
                    "question": "SOL ETF?",
                    "yes_price": [0.30] * 24 + [0.41, 0.42, 0.43, 0.44, 0.45, 0.46],
                }
            ),
            pd.DataFrame(
                {
                    "timestamp": timestamps,
                    "family": "xrp_etf",
                    "slug": "xrp-market",
                    "question": "XRP ETF?",
                    "yes_price": [0.20] * 24 + [0.32, 0.33, 0.34, 0.35, 0.36, 0.37],
                }
            ),
        ],
        ignore_index=True,
    )
    spec = StrategySpec(name="test", delta_threshold=0.10, level_threshold=0.55, hold_hours=72)

    signals = build_alt_etf_signals(hourly, spec)

    assert len(signals) == 6
    assert set(signals["asset"]) == {"ETH"}
    assert signals.iloc[0]["timestamp"] == timestamps[24]
    assert signals.iloc[0]["entry_time"] == timestamps[25]
    assert signals.iloc[0]["exit_time"] == timestamps[25] + pd.Timedelta(hours=72)
    assert (signals["delta_24h"] >= 0.10).all()


def test_build_alt_etf_signals_sorts_across_assets_by_entry_time():
    timestamps = pd.date_range("2025-01-01", periods=30, freq="h", tz="UTC")
    hourly = pd.concat(
        [
            pd.DataFrame(
                {
                    "timestamp": timestamps,
                    "family": "eth_etf",
                    "slug": "eth-market",
                    "question": "ETH ETF?",
                    "yes_price": [0.40] * 24 + [0.56, 0.57, 0.58, 0.59, 0.60, 0.61],
                }
            ),
            pd.DataFrame(
                {
                    "timestamp": timestamps,
                    "family": "xrp_etf",
                    "slug": "xrp-market",
                    "question": "XRP ETF?",
                    "yes_price": [0.20] * 23 + [0.20, 0.31, 0.32, 0.33, 0.34, 0.35, 0.36],
                }
            ),
        ],
        ignore_index=True,
    )
    spec = StrategySpec(name="test", delta_threshold=0.10, level_threshold=0.30, hold_hours=48)

    signals = build_alt_etf_signals(hourly, spec)

    assert signals["entry_time"].is_monotonic_increasing
    assert {"ETH", "XRP"}.issubset(set(signals["asset"]))
    grouped = signals.groupby("asset", sort=False)["entry_time"].min()
    assert grouped["ETH"] <= grouped["XRP"]
