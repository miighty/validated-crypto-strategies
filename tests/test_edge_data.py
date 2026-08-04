from edge_research.data import merge_dataset_reports, normalize_symbols
from edge_research.experiments import manual_experiment_id


def test_manual_base_tickers_default_to_usdt_and_preserve_pairs():
    assert normalize_symbols(["sol", "ETC", "btc/usdt", "ETHBTC"]) == [
        "SOLUSDT",
        "ETCUSDT",
        "BTCUSDT",
        "ETHBTC",
    ]


def test_symbol_normalization_accepts_commas_and_trailing_slash():
    assert normalize_symbols(["SOL, ETC", "btc/", "SOL"]) == [
        "SOLUSDT",
        "ETCUSDT",
        "BTCUSDT",
    ]


def test_manual_download_manifest_upserts_without_dropping_existing_markets():
    existing = [
        {"symbol": "BTCUSDT", "rows": 10},
        {"symbol": "SOLUSDT", "rows": 8},
    ]
    fresh = [
        {"symbol": "SOLUSDT", "rows": 12},
        {"symbol": "ETCUSDT", "rows": 9},
    ]
    assert merge_dataset_reports(existing, fresh) == [
        {"symbol": "BTCUSDT", "rows": 10},
        {"symbol": "ETCUSDT", "rows": 9},
        {"symbol": "SOLUSDT", "rows": 12},
    ]


def test_manual_universe_gets_a_stable_noncanonical_experiment_id():
    assert manual_experiment_id("EXP-BO-001", ["SOLUSDT", "ETCUSDT"]) == (
        "EXP-BO-001-MANUAL-SOLUSDT-ETCUSDT"
    )
