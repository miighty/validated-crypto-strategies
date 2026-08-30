# Delta-Neutral Single-Asset Funding-Carry Harvest Validation

## Primary rule
> Single-asset delta-neutral cash-and-carry (long spot + short perp, equal notional). Enter/remain hedged while the trailing mean of the last 3 completed 8h funding prints >= +30bps/24h-equivalent (+3bps/8h mean); exit to fully unhedged cash-equivalent (flat, no position, no price exposure) when that trailing mean falls below +1bps/8h (hysteresis band). While hedged, capital compounds by the realized funding print each 8h; no price risk is modeled while hedged (idealized 1:1 hedge, no basis/liquidation risk, no separate margin financing spread).

## Honesty disclosures
- No margin/borrow financing spread modeled for the short-perp leg beyond the funding print itself.
- Assumed a continuously maintained 1:1 hedge with no basis or liquidation risk while positioned.
- Real data only: Binance real 8h funding history + real 1h spot OHLCV, already cached in this repo.

## Per-asset results

### BTC
| strategy | asset | final_capital | total_return_pct | sharpe | sortino | max_drawdown_pct |
| --- | --- | --- | --- | --- | --- | --- |
| cash | BTC | 10000.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| timed_delta_neutral_carry | BTC | 13804.1555 | 38.0416 | 7.5495 | 14.3969 | -0.5700 |
| always_on_delta_neutral_carry | BTC | 18239.0142 | 82.3901 | 16.4847 | 62.8706 | -0.4434 |
| buy_and_hold | BTC | 22009.8132 | 120.0981 | 0.1891 | 0.2667 | -77.1985 |
| daily_dca | BTC | 15105.4467 | 51.0545 |  | inf | -53.9954 |

- Trades: **6**, time hedged: **16.5%**
- Doubled-cost final capital: **$13313.88**
- Best-trade-exclusion final capital: **$11214.58** (best trade = 66.38609006479751% of total PnL)
- Verdict: **REJECTED**

Partition breakdown:
| asset | partition | n_prints | n_trades | final_capital | total_return_pct |
| --- | --- | --- | --- | --- | --- |
| BTC | development_pre_2024 | 3283 | 4 | 13097.0199 | 30.9702 |
| BTC | validation_2024 | 1098 | 3 | 10508.3013 | 5.0830 |
| BTC | test_2025_onward | 1719 | 0 | 10000.0000 | 0.0000 |

### ETH
| strategy | asset | final_capital | total_return_pct | sharpe | sortino | max_drawdown_pct |
| --- | --- | --- | --- | --- | --- | --- |
| cash | ETH | 10000.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| timed_delta_neutral_carry | ETH | 15085.4946 | 50.8549 | 8.0846 | 17.5422 | -0.5616 |
| always_on_delta_neutral_carry | ETH | 19025.5963 | 90.2560 | 13.5585 | 38.2332 | -1.7773 |
| buy_and_hold | ETH | 25660.5668 | 156.6057 | 0.2144 | 0.2997 | -81.3430 |
| daily_dca | ETH | 8602.2379 | -13.9776 |  | inf | -71.3804 |

- Trades: **7**, time hedged: **20.5%**
- Doubled-cost final capital: **$14462.28**
- Best-trade-exclusion final capital: **$11592.45** (best trade = 64.49575746853564% of total PnL)
- Verdict: **REJECTED**

Partition breakdown:
| asset | partition | n_prints | n_trades | final_capital | total_return_pct |
| --- | --- | --- | --- | --- | --- |
| ETH | development_pre_2024 | 3283 | 5 | 14237.4762 | 42.3748 |
| ETH | validation_2024 | 1098 | 3 | 10563.8372 | 5.6384 |
| ETH | test_2025_onward | 1719 | 0 | 10000.0000 | 0.0000 |

### SOL
| strategy | asset | final_capital | total_return_pct | sharpe | sortino | max_drawdown_pct |
| --- | --- | --- | --- | --- | --- | --- |
| cash | SOL | 10000.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| timed_delta_neutral_carry | SOL | 14500.4785 | 45.0048 | 6.6778 | 11.6217 | -0.8550 |
| always_on_delta_neutral_carry | SOL | 10395.0142 | 3.9501 | 0.2593 | 0.2701 | -35.3559 |
| buy_and_hold | SOL | 491044.9808 | 4810.4498 | 0.4165 | 0.6144 | -96.7962 |
| daily_dca | SOL | 19664.5877 | 96.6459 |  | inf | -95.1682 |

- Trades: **12**, time hedged: **19.0%**
- Doubled-cost final capital: **$13488.75**
- Best-trade-exclusion final capital: **$13704.59** (best trade = 21.725746835452746% of total PnL)
- Verdict: **CANDIDATE**

Partition breakdown:
| asset | partition | n_prints | n_trades | final_capital | total_return_pct |
| --- | --- | --- | --- | --- | --- |
| SOL | development_pre_2024 | 3358 | 10 | 13433.0483 | 34.3305 |
| SOL | validation_2024 | 1098 | 3 | 10762.2461 | 7.6225 |
| SOL | test_2025_onward | 1719 | 0 | 10000.0000 | 0.0000 |

### XRP
| strategy | asset | final_capital | total_return_pct | sharpe | sortino | max_drawdown_pct |
| --- | --- | --- | --- | --- | --- | --- |
| cash | XRP | 10000.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| timed_delta_neutral_carry | XRP | 17075.6295 | 70.7563 | 8.6615 | 23.7602 | -0.5772 |
| always_on_delta_neutral_carry | XRP | 20643.0146 | 106.4301 | 12.2668 | 44.9526 | -2.4645 |
| buy_and_hold | XRP | 48490.1036 | 384.9010 | 0.2746 | 0.3984 | -84.8279 |
| daily_dca | XRP | 15583.7860 | 55.8379 |  | inf | -70.3289 |

- Trades: **6**, time hedged: **19.0%**
- Doubled-cost final capital: **$16469.16**
- Best-trade-exclusion final capital: **$12014.36** (best trade = 63.00229121584906% of total PnL)
- Verdict: **REJECTED**

Partition breakdown:
| asset | partition | n_prints | n_trades | final_capital | total_return_pct |
| --- | --- | --- | --- | --- | --- |
| XRP | development_pre_2024 | 3283 | 4 | 15917.8795 | 59.1788 |
| XRP | validation_2024 | 1098 | 3 | 10695.1448 | 6.9514 |
| XRP | test_2025_onward | 1719 | 0 | 10000.0000 | 0.0000 |

## Sensitivity grid (final capital, $10,000 start)
| asset | lookback_prints | entry_threshold | exit_threshold | n_trades | final_capital | total_return_pct |
| --- | --- | --- | --- | --- | --- | --- |
| BTC | 3 | 0.0002 | 0.0001 | 8 | 14386.2773 | 43.8628 |
| BTC | 3 | 0.0003 | 0.0001 | 6 | 13804.1555 | 38.0416 |
| BTC | 3 | 0.0005 | 0.0002 | 13 | 11841.9589 | 18.4196 |
| BTC | 9 | 0.0003 | 0.0001 | 6 | 13391.1264 | 33.9113 |
| BTC | 9 | 0.0005 | 0.0002 | 6 | 11942.3247 | 19.4232 |
| ETH | 3 | 0.0002 | 0.0001 | 7 | 15468.3369 | 54.6834 |
| ETH | 3 | 0.0003 | 0.0001 | 7 | 15085.4946 | 50.8549 |
| ETH | 3 | 0.0005 | 0.0002 | 14 | 12444.9485 | 24.4495 |
| ETH | 9 | 0.0003 | 0.0001 | 5 | 14403.6477 | 44.0365 |
| ETH | 9 | 0.0005 | 0.0002 | 5 | 13087.8920 | 30.8789 |
| SOL | 3 | 0.0002 | 0.0001 | 11 | 15001.6727 | 50.0167 |
| SOL | 3 | 0.0003 | 0.0001 | 12 | 14500.4785 | 45.0048 |
| SOL | 3 | 0.0005 | 0.0002 | 21 | 11854.7993 | 18.5480 |
| SOL | 9 | 0.0003 | 0.0001 | 9 | 14270.0907 | 42.7009 |
| SOL | 9 | 0.0005 | 0.0002 | 11 | 12194.1322 | 21.9413 |
| XRP | 3 | 0.0002 | 0.0001 | 8 | 17295.5710 | 72.9557 |
| XRP | 3 | 0.0003 | 0.0001 | 6 | 17075.6295 | 70.7563 |
| XRP | 3 | 0.0005 | 0.0002 | 22 | 13677.3508 | 36.7735 |
| XRP | 9 | 0.0003 | 0.0001 | 6 | 16684.2826 | 66.8428 |
| XRP | 9 | 0.0005 | 0.0002 | 10 | 14373.2017 | 43.7320 |

## Overall verdict
1/4 assets cleared all gates (beat cash, beat always-on carry, survive doubled cost, survive best-trade exclusion, concentration < 100% of PnL).

**PROMISING BUT INCONCLUSIVE** — mixed results across assets.
