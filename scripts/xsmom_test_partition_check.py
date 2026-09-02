import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from xsmom_longonly_largeuniverse_validation import (
    discover_universe, load_field, eligibility_mask, build_momentum_score,
    run_backtest, compute_metrics, ROUND_TRIP_COST, TEST_START, INITIAL_CAPITAL,
    equal_weight_universe_bh, buy_and_hold, BENCH_ASSETS,
)

universe = discover_universe()
closes = load_field(universe, "close")
opens = load_field(universe, "open")
eligible = eligibility_mask(closes)
score = build_momentum_score(closes)

primary = run_backtest(score, eligible, opens, "primary")
trades = primary["trades"].sort_values("rebalance_date").reset_index(drop=True)

test_trades = trades[trades["entry_date"] >= TEST_START].reset_index(drop=True)
print("n test trades:", len(test_trades))

capital = INITIAL_CAPITAL
for _, row in test_trades.iterrows():
    capital = capital * (1 + row["weighted_return"]) - row["turnover_frac"] * ROUND_TRIP_COST * capital
print("test-partition-only compounded final (rebased $10k at test start):", capital)
print("test partition total return:", capital / INITIAL_CAPITAL - 1)

# benchmarks over the same test window
closes_test = closes[closes.index >= TEST_START]
ew_bh_test = equal_weight_universe_bh(closes_test)
print("equal-weight universe BH over test window:", ew_bh_test["final_capital"], ew_bh_test["total_return"])
for coin in BENCH_ASSETS:
    if coin in closes_test.columns:
        r = buy_and_hold(closes_test, coin)
        print(f"{coin} BH over test window:", r["final_capital"], r["total_return"])
