# BTC Dominance and ETF Flow Validation

Run:

```bash
uv run crypto-regime-backtest validate-dominance-etf
```

## Latest status

- **Blocked by missing real point-in-time source files.**
- Latest run stayed fail-closed and produced **no proxy charts or simulated ETF flows**.
- Missing inputs were exactly:
  - `data/dominance_etf/dominance.csv`
  - `data/dominance_etf/alt_universe.csv.gz`
  - `data/dominance_etf/etf_flows.csv`

Artifacts from the latest run:

- `results/dominance_etf/runs/run-20260808T022718Z/RANKED_REPORT.md`
- `results/dominance_etf/runs/run-20260808T022718Z/results.csv`

## Input contracts

Put these files in `data/dominance_etf/`:

| File | Required columns | Timing rule |
| --- | --- | --- |
| `dominance.csv` | `timestamp,available_at,btc_dominance,alt_market_cap_ex_btc,total3_market_cap,source_url` | `available_at` is the original publication time and cannot precede `timestamp`. |
| `alt_universe.csv.gz` | `timestamp,symbol,close,market_cap,tradeable,stablecoin,perpetual_tradeable` | One row per asset/date; tradeability, perp availability and market cap are known at that date. |
| `etf_flows.csv` | `flow_date,published_at,asset,fund,net_flow_usd,total_assets_usd,source_url` | `published_at` is the original public-release time, never an assumed end-of-day time. |

The workflow charts dominance, BTC/ETH, the actually tradeable alt-universe market cap and published ETF flows before it evaluates predeclared signals. Dominance variants cover equal-weight top 10/20/50, cap-weighted, large/mid/high-beta, ETH and point-in-time perpetual baskets, plus long-BTC/short-alt and short-ETH/BTC relative-value forms. A pass requires at least 20 non-overlapping events, positive untouched-test mean, a positive bootstrap lower bound and positive results in at least two regimes. Costs are charged at entry and exit.
