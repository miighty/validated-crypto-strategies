import pandas as pd

from edge_research.config import ExecutionConfig
from edge_research.engine import ExitRules, run_symbol_backtest


def _frame(opens, highs=None, lows=None, closes=None):
    opens = [float(value) for value in opens]
    closes = opens if closes is None else [float(value) for value in closes]
    highs = [max(o, c) + 1 for o, c in zip(opens, closes)] if highs is None else highs
    lows = [min(o, c) - 1 for o, c in zip(opens, closes)] if lows is None else lows
    index = pd.date_range("2024-01-01", periods=len(opens), freq="4h", tz="UTC")
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": 1.0},
        index=index,
    )


def _signals(frame, entries, atr=10.0):
    return pd.DataFrame(
        {"entry": entries, "exit": False, "atr": atr, "level": float("nan")},
        index=frame.index,
    )


def test_signal_executes_at_next_open():
    frame = _frame([90, 100, 110])
    result = run_symbol_backtest(
        frame,
        "TEST",
        _signals(frame, [1, 0, 0]),
        ExecutionConfig(initial_capital=1000, fee_rate=0, slippage_rate=0),
        ExitRules(1, None),
    )
    trade = result.trades.iloc[0]
    assert trade["signal_timestamp"] == frame.index[0]
    assert trade["entry_timestamp"] == frame.index[1]
    assert trade["entry_price"] == 100


def test_manually_calculable_long_return_and_equity():
    frame = _frame([90, 100, 110], closes=[90, 105, 110])
    result = run_symbol_backtest(
        frame,
        "TEST",
        _signals(frame, [1, 0, 0]),
        ExecutionConfig(initial_capital=1000, fee_rate=0.001, slippage_rate=0),
        ExitRules(1, None),
    )
    trade = result.trades.iloc[0]
    assert abs(trade["gross_return"] - 0.10) < 1e-12
    assert abs(trade["fees"] - 2.10) < 1e-12
    assert abs(trade["net_return"] - 0.0979) < 1e-12
    assert abs(result.equity.iloc[-1] - 1097.9) < 1e-12


def test_manually_calculable_short_return():
    frame = _frame([110, 100, 90], closes=[110, 95, 90])
    result = run_symbol_backtest(
        frame,
        "TEST",
        _signals(frame, [-1, 0, 0]),
        ExecutionConfig(initial_capital=1000, fee_rate=0.001, slippage_rate=0),
        ExitRules(1, None),
    )
    trade = result.trades.iloc[0]
    assert abs(trade["gross_return"] - 0.10) < 1e-12
    assert abs(trade["fees"] - 1.90) < 1e-12
    assert abs(trade["net_return"] - 0.0981) < 1e-12


def test_fee_is_applied_on_entry_and_exit():
    frame = _frame([100, 100, 100])
    result = run_symbol_backtest(
        frame,
        "TEST",
        _signals(frame, [1, 0, 0]),
        ExecutionConfig(initial_capital=1000, fee_rate=0.001, slippage_rate=0),
        ExitRules(1, None),
    )
    trade = result.trades.iloc[0]
    assert abs(trade["fees"] - 2.0) < 1e-12
    assert abs(trade["net_return"] + 0.002) < 1e-12


def test_atr_stop_uses_conservative_intrabar_fill():
    frame = _frame([90, 100, 100], highs=[91, 101, 101], lows=[89, 94, 99])
    result = run_symbol_backtest(
        frame,
        "TEST",
        _signals(frame, [1, 0, 0], atr=5.0),
        ExecutionConfig(initial_capital=1000, fee_rate=0, slippage_rate=0),
        ExitRules(10, 1.0),
    )
    trade = result.trades.iloc[0]
    assert trade["exit_reason"] == "atr_stop"
    assert trade["exit_price"] == 95
    assert result.equity.iloc[-1] == 950


def test_overlapping_signals_do_not_create_overlapping_trades():
    frame = _frame([100, 100, 101, 102, 103, 104])
    result = run_symbol_backtest(
        frame,
        "TEST",
        _signals(frame, [1, 1, 1, 0, 0, 0]),
        ExecutionConfig(initial_capital=1000, fee_rate=0, slippage_rate=0),
        ExitRules(2, None),
    )
    assert len(result.trades) == 1
    assert result.trades.iloc[0]["holding_period_bars"] == 2
