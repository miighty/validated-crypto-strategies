import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from xsmom_longonly_largeuniverse_validation import (
    discover_universe, load_field, eligibility_mask, build_momentum_score,
    run_backtest, run_random_control, compute_metrics, ROUND_TRIP_COST,
)

universe = discover_universe()
closes = load_field(universe, "close")
opens = load_field(universe, "open")
eligible = eligibility_mask(closes)
score = build_momentum_score(closes)

primary = run_backtest(score, eligible, opens, "primary")
primary_final = primary["final_capital"]
print("primary final:", primary_final)

n_trials = 200
finals = []
for seed in range(n_trials):
    ctrl = run_random_control(score.index, eligible, opens, seed=100000 + seed)
    finals.append(ctrl["final_capital"])
finals = np.array(finals)
p_value = (finals >= primary_final).mean()
print(f"MC label-scramble n_trials={n_trials}: mean={finals.mean():.0f} std={finals.std():.0f} "
      f"p(random >= primary)={p_value:.4f}")
print(f"primary percentile among random draws: {(finals < primary_final).mean()*100:.2f}")

# best/second-best block exclusion sensitivity
trades = primary["trades"].sort_values("rebalance_date").reset_index(drop=True)
sorted_idx = trades["net_pnl"].sort_values(ascending=False).index.tolist()
for k in [1, 2, 3]:
    excl_idx = set(sorted_idx[:k])
    capital = 10000.0
    for i, row in trades.iterrows():
        if i in excl_idx:
            continue
        capital = capital * (1 + row["weighted_return"]) - row["turnover_frac"] * ROUND_TRIP_COST * capital
    print(f"excluding top {k} blocks -> final capital {capital:.0f}")
