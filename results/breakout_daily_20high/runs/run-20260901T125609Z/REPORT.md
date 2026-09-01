# Plain Daily 20-Day-High / 10-Day-Low Breakout Continuation -- Full Validation

## Primary rule
> LONG-ONLY: enter at next daily open when close breaks above the trailing prior-only 20-day high. Exit at next daily open on the first close below the trailing prior-only 10-day low. Flat otherwise, non-overlapping trades. 30bps round-trip cost.

## Data sources
- Real Binance spot 1d OHLCV (already cached, `data/raw/*_1d.csv.gz`). No OI dependency, no synthetic data.

## Per-asset results
### BTC
- Trades: **62** (mean hold 20.1d)
- Primary final capital: **$86,092.91** (start $10,000)
- Buy-and-hold final: **$46,414.40**
- Daily DCA final: **$40,001.66**
- Seeded random-timing control final: **$24,002.59** (62 trades)
- Doubled-cost final: **$78,430.85**
- 1-bar delayed-execution final: **$72,309.01** (62 trades)
- Best-trade-exclusion final: **$49,316.09**
- Top single-trade % of total PnL: **8.387993857507341**
- Walk-forward split: {'first_half_sharpe': 1.565571244155051, 'second_half_sharpe': 1.3125516432240139, 'n_first': 31, 'n_second': 31}
- Monte Carlo bootstrap-null test: {'observed_sharpe': 2.052003311607568, 'null_sharpe_std': 1.072771046975165, 'p_value': 0.06, 'n_trials': 2000}
- Deflated Sharpe (n_trials=96): {'sr_annualized': 1.1114463242878632, 'sr_per_bar': 0.2606046811789726, 'se_per_bar': 0.09869661321182921, 'n_obs': 62, 'n_trials': 96, 'dsr_stat': 0.1242554713225286, 'dsr_p_value': 0.45055650136650705, 'passes_at_0.05': False}
- Gates: {'beats_cash': True, 'beats_bh': True, 'beats_dca': True, 'beats_random_control': True, 'survives_doubled_cost': True, 'survives_best_trade_exclusion': True, 'survives_1bar_delay': True, 'concentration_ok': True, 'has_holdout_trades': True, 'monte_carlo_significant': False, 'deflated_sharpe_passes': False}
- Verdict: **REJECTED**

Partition breakdown:
| asset | partition | n_trades | mean_trade_return_pct |
| --- | --- | --- | --- |
| BTC | development_pre_2024 | 44 | 5.5513 |
| BTC | validation_2024 | 8 | 8.9578 |
| BTC | test_2025_onward | 10 | 1.1925 |

### ETH
- Trades: **62** (mean hold 18.8d)
- Primary final capital: **$177,993.91** (start $10,000)
- Buy-and-hold final: **$25,779.94**
- Daily DCA final: **$34,806.07**
- Seeded random-timing control final: **$58,015.86** (62 trades)
- Doubled-cost final: **$162,152.88**
- 1-bar delayed-execution final: **$176,985.48** (62 trades)
- Best-trade-exclusion final: **$75,412.04**
- Top single-trade % of total PnL: **29.884045036844125**
- Walk-forward split: {'first_half_sharpe': 2.1834407367729445, 'second_half_sharpe': 0.44624037270059197, 'n_first': 31, 'n_second': 31}
- Monte Carlo bootstrap-null test: {'observed_sharpe': 2.1386333952452046, 'null_sharpe_std': 1.129006436981815, 'p_value': 0.067, 'n_trials': 2000}
- Deflated Sharpe (n_trials=96): {'sr_annualized': 1.1959417715046246, 'sr_per_bar': 0.2716067128029896, 'se_per_bar': 0.08629775377093823, 'n_obs': 62, 'n_trials': 96, 'dsr_stat': 0.6311139929301955, 'dsr_p_value': 0.26398299621662313, 'passes_at_0.05': False}
- Gates: {'beats_cash': True, 'beats_bh': True, 'beats_dca': True, 'beats_random_control': True, 'survives_doubled_cost': True, 'survives_best_trade_exclusion': True, 'survives_1bar_delay': True, 'concentration_ok': False, 'has_holdout_trades': True, 'monte_carlo_significant': False, 'deflated_sharpe_passes': False}
- Verdict: **REJECTED**

Partition breakdown:
| asset | partition | n_trades | mean_trade_return_pct |
| --- | --- | --- | --- |
| ETH | development_pre_2024 | 42 | 10.3398 |
| ETH | validation_2024 | 9 | 1.4530 |
| ETH | test_2025_onward | 11 | 1.0865 |

### SOL
- Trades: **43** (mean hold 17.6d)
- Primary final capital: **$906,379.20** (start $10,000)
- Buy-and-hold final: **$259,960.94**
- Daily DCA final: **$40,676.96**
- Seeded random-timing control final: **$155,041.16** (43 trades)
- Doubled-cost final: **$849,639.63**
- 1-bar delayed-execution final: **$1,974,151.51** (43 trades)
- Best-trade-exclusion final: **$205,694.63**
- Top single-trade % of total PnL: **12.419470861788245**
- Walk-forward split: {'first_half_sharpe': 1.3905418921605992, 'second_half_sharpe': 1.3875625088761365, 'n_first': 21, 'n_second': 22}
- Monte Carlo bootstrap-null test: {'observed_sharpe': 1.955757060989656, 'null_sharpe_std': 1.5938119398388855, 'p_value': 0.115, 'n_trials': 2000}
- Deflated Sharpe (n_trials=96): {'sr_annualized': 1.3585076221074903, 'sr_per_bar': 0.29825015571881924, 'se_per_bar': 0.0879547309683965, 'n_obs': 43, 'n_trials': 96, 'dsr_stat': 0.8747439140473365, 'dsr_p_value': 0.19085663012136855, 'passes_at_0.05': False}
- Gates: {'beats_cash': True, 'beats_bh': True, 'beats_dca': True, 'beats_random_control': True, 'survives_doubled_cost': True, 'survives_best_trade_exclusion': True, 'survives_1bar_delay': True, 'concentration_ok': True, 'has_holdout_trades': True, 'monte_carlo_significant': False, 'deflated_sharpe_passes': False}
- Verdict: **REJECTED**

Partition breakdown:
| asset | partition | n_trades | mean_trade_return_pct |
| --- | --- | --- | --- |
| SOL | development_pre_2024 | 25 | 38.2046 |
| SOL | validation_2024 | 7 | 11.2825 |
| SOL | test_2025_onward | 11 | 1.2453 |

### XRP
- Trades: **54** (mean hold 16.6d)
- Primary final capital: **$83,657.29** (start $10,000)
- Buy-and-hold final: **$21,290.06**
- Daily DCA final: **$22,418.70**
- Seeded random-timing control final: **$404.04** (54 trades)
- Doubled-cost final: **$77,134.13**
- 1-bar delayed-execution final: **$75,630.57** (54 trades)
- Best-trade-exclusion final: **$22,557.01**
- Top single-trade % of total PnL: **97.92884132421821**
- Walk-forward split: {'first_half_sharpe': 1.125193441363266, 'second_half_sharpe': 0.9799687992798448, 'n_first': 27, 'n_second': 27}
- Monte Carlo bootstrap-null test: {'observed_sharpe': 1.4450725595233416, 'null_sharpe_std': 1.6202568627938962, 'p_value': 0.23, 'n_trials': 2000}
- Deflated Sharpe (n_trials=96): {'sr_annualized': 0.9210960517817041, 'sr_per_bar': 0.1966494673405477, 'se_per_bar': 0.08361951735795448, 'n_obs': 54, 'n_trials': 96, 'dsr_stat': -0.1644894555982513, 'dsr_p_value': 0.565327076547566, 'passes_at_0.05': False}
- Gates: {'beats_cash': True, 'beats_bh': True, 'beats_dca': True, 'beats_random_control': True, 'survives_doubled_cost': True, 'survives_best_trade_exclusion': True, 'survives_1bar_delay': True, 'concentration_ok': False, 'has_holdout_trades': True, 'monte_carlo_significant': False, 'deflated_sharpe_passes': False}
- Verdict: **REJECTED**

Partition breakdown:
| asset | partition | n_trades | mean_trade_return_pct |
| --- | --- | --- | --- |
| XRP | development_pre_2024 | 39 | 5.7029 |
| XRP | validation_2024 | 5 | 61.2276 |
| XRP | test_2025_onward | 10 | -0.0660 |

## Overall verdict
0/4 assets cleared every gate.

**REJECTED** -- no asset cleared every gate.