# BTC/ETH Quarterly Futures Basis Cash-and-Carry Validation

Run artifact: `/Users/vr/Documents/Projects/validated-crypto-strategies/results/quarterly_basis_carry/runs/run-20260831T064209Z`

## Primary rule

> At each real Binance daily close, if the current-quarter futures contract's annualized basis (log-linear extrapolation of (future_close/spot_close - 1) to a 365-day year) is >= 8%, enter a delta-neutral cash-and-carry trade (long spot + short the quarterly future, equal notional) at next day's open with the full accrued reserve; hold to contract expiry (basis converges to zero by settlement), realize the captured basis net of 4-leg round-trip costs (spot buy/sell + futures short/cover), then wait 1 day before re-evaluating.

## Result summary (per asset)

| asset | strategy | final_equity | invested_total | net_return | trade_count | win_rate | top_trade_pnl_share |
|---|---|---|---|---|---|---|---|
| BTC | quarterly_basis_carry | 10067.2 | 10000 | 0.00671964 | 5 | 1 | 0.420012 |
| BTC | quarterly_basis_carry_doubled_cost | 10042.1 | 10000 | 0.00420505 | 5 | 0.8 | 0.423761 |
| BTC | quarterly_basis_carry_zero_cost | 10092.6 | 10000 | 0.00926325 | 5 | 1 | 0.418931 |
| BTC | quarterly_basis_carry_no_best_trade | 10039 | 10000 | 0.00389731 | 4 | 1 | 0.4685 |
| BTC | cash | 10000 | 10000 | 0 | 0 | nan | nan |
| BTC | dca_spot_close | 15043.1 | 10000 | 0.504313 | 2001 | nan | nan |
| BTC | dca_spot_open | 15047.1 | 10000 | 0.504711 | 2001 | nan | nan |
| ETH | quarterly_basis_carry | 10049.4 | 10000 | 0.00494054 | 7 | 0.714286 | 0.602222 |
| ETH | quarterly_basis_carry_doubled_cost | 9980.45 | 10000 | -0.00195486 | 7 | 0.714286 | -0.988419 |
| ETH | quarterly_basis_carry_zero_cost | 10119.5 | 10000 | 0.0119493 | 7 | 1 | 0.337755 |
| ETH | quarterly_basis_carry_no_best_trade | 10019.9 | 10000 | 0.00198682 | 6 | 0.666667 | 0.983423 |
| ETH | cash | 10000 | 10000 | 0 | 0 | nan | nan |
| ETH | dca_spot_close | 8469.97 | 10000 | -0.153003 | 2000 | nan | nan |
| ETH | dca_spot_open | 8470.67 | 10000 | -0.152933 | 2000 | nan | nan |

## Partition breakdown

| asset | partition | trade_count | net_return | win_rate | top_trade_pnl_share |
|---|---|---|---|---|---|
| BTC | development | 5 | 0.012661 | 1 | 0.420012 |
| BTC | validation | 4 | 0.0447407 | 1 | 0.416244 |
| BTC | holdout | 0 | 1.11022e-15 | nan | nan |
| ETH | development | 7 | 0.00931298 | 0.714286 | 0.602222 |
| ETH | validation | 4 | 0.0434566 | 1 | 0.412793 |
| ETH | holdout | 0 | 0 | nan | nan |

## Verdict per asset

- **BTC**: REJECTED -- carry net_return=0.0067 vs spot B&H=0.5043, 5 trades (0 in holdout), top-trade PnL share=0.42
  - zero trades in holdout partition (2025-06 onward)
- **ETH**: REJECTED -- carry net_return=0.0049 vs spot B&H=-0.1530, 7 trades (0 in holdout), top-trade PnL share=0.60
  - fails doubled-cost check (loses to cash)
  - zero trades in holdout partition (2025-06 onward)

