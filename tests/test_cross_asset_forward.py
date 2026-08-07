import json

import pandas as pd
import pytest

from edge_research.cross_asset_forward import (
    FROZEN_STRATEGY,
    append_observations,
    forward_status,
    load_forward_config,
    read_ledger,
)


def config():
    return {
        "experiment_id": "FORWARD-TEST",
        "first_eligible_session": "2026-08-05",
        "strategy": FROZEN_STRATEGY.copy(),
        "universe": {"benchmarks": ["SPY", "QQQ"], "equities": ["MSTR"]},
        "promotion_gate": {
            "minimum_new_event_sessions": 2,
            "require_positive_total_return": True,
            "require_bootstrap_lower_bound_above_zero": True,
            "require_positive_50bps_stress_return": True,
            "require_positive_liquid_session_return": True,
            "liquid_session_minimum_minutes": 300,
            "maximum_single_event_profit_share": 0.75,
        },
        "safety": {"order_submission": "prohibited"},
    }


def observation(session, lock_id, value=0.01):
    return {
        "experiment_id": "FORWARD-TEST",
        "lock_id": lock_id,
        "session": session,
        "recorded_at_utc": "2026-08-05T20:10:00+00:00",
        "classification": "wild_event",
        "btc_event_return": 0.05,
        "wild_threshold": 0.04,
        "eligible_asset_slots": 1,
        "positions_opened": 1,
        "portfolio_return_20bps": value,
        "portfolio_return_50bps": value - 0.003,
        "liquid_portfolio_return_20bps": value,
        "trades": [],
    }


def test_append_only_ledger_is_hash_chained(tmp_path):
    from edge_research.cross_asset_forward import semantic_lock_id

    cfg = config()
    lock_id = semantic_lock_id(cfg)
    ledger = tmp_path / "ledger.jsonl"
    assert append_observations(ledger, [observation("2026-08-05", lock_id)]) == 1
    assert append_observations(ledger, [observation("2026-08-05", lock_id)]) == 0
    assert len(read_ledger(ledger)) == 1
    damaged = json.loads(ledger.read_text())
    damaged["portfolio_return_20bps"] = 99
    ledger.write_text(json.dumps(damaged) + "\n")
    with pytest.raises(ValueError, match="hash chain"):
        read_ledger(ledger)


def test_forward_gate_requires_enough_independent_events():
    from edge_research.cross_asset_forward import semantic_lock_id

    cfg = config()
    record = observation("2026-08-05", semantic_lock_id(cfg))
    status = forward_status([record], cfg)
    assert status["new_event_sessions"] == 1
    assert not status["ready_for_independent_review"]
    assert not status["live_trading_approved"]


def test_modified_strategy_config_is_rejected(tmp_path):
    cfg = config()
    cfg["strategy"]["wild_event_quantile"] = 0.90
    path = tmp_path / "config.yaml"
    path.write_text(pd.Series(cfg).to_json())
    with pytest.raises(ValueError, match="differ"):
        load_forward_config(path)
