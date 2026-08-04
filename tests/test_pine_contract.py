from pathlib import Path

from edge_research.verify import verify_pine_contract, verify_tradingview_record

ROOT = Path(__file__).resolve().parents[1]


def test_rsi_pine_contract_prevents_same_close_and_recalculation_lookahead():
    path = ROOT / "pine" / "rsi_mean_reversion_strategy.pine"
    verify_pine_contract(path, "rsi_mean_reversion")


def test_breakout_pine_contract_excludes_current_high():
    path = ROOT / "pine" / "breakout_acceptance_rejection_strategy.pine"
    verify_pine_contract(path, "breakout_acceptance_rejection")


def test_tradingview_records_cover_forward_default_universe():
    for experiment_id in ("EXP-2026-08-04-RSI-001", "EXP-2026-08-04-BO-001"):
        path = ROOT / "reports" / "tradingview" / f"{experiment_id}.json"
        assert verify_tradingview_record(path) == (
            "SUPPLEMENTARY_FORWARD_TESTED_HISTORICAL_WINDOWS_DEFERRED"
        )
