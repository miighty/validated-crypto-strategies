# Order-Book Depth-Confirmed Daily Breakout Validation

## Primary rule
> Enter at next daily open when close breaks above the prior-only 20-day high AND the same day's real Binance futures order-book depth imbalance z-score is >= +0.5 vs its own prior-only trailing 90-day history. Exit at next daily open on the first close below the prior-only 10-day low. Non-overlapping, 30bps round-trip cost.

## Data sources
- Real Binance spot daily OHLCV: `data/raw/*_1d.csv.gz`
- Real Binance USD-M public order-book depth archive aggregated to daily imbalance: `data/orderbook_depth/*_depth_imbalance_1d.csv.gz`

## Per-asset results
### BTC
- Combined breakout+depth signals: **17** raw / **10** executed trades
- Filtered final capital: **$16,445.37**
- Unfiltered breakout control final: **$34,302.11**
- Buy-and-hold final: **$38,484.62**
- Daily DCA final: **$12,457.93**
- Random-timing control final: **$16,000.72** (10 trades)
- Doubled-cost final: **$16,199.98**
- 1-bar delayed final: **$16,930.75** (10 trades)
- Best-trade-exclusion final: **$12,225.89**
- Top single-trade % of total PnL: **59.6143057293858**
- Walk-forward: {'first_half_sharpe': 1.0468641597184882, 'second_half_sharpe': 0.5622594602068494, 'n_first': 5, 'n_second': 5}
- Monte Carlo: {'observed_sharpe': 1.2259708883204112, 'null_sharpe_std': 1.9997960698056114, 'p_value': 0.2605, 'n_trials': 2000}
- Deflated Sharpe: {'sr_annualized': 1.5725294323905765, 'sr_per_bar': 0.3876860352152419, 'se_per_bar': 0.2712901220827667, 'n_obs': 10, 'n_trials': 97, 'dsr_stat': -1.0908217501340973, 'dsr_p_value': 0.8623243380113064, 'passes_at_0.05': False}
- Gates: {'beats_unfiltered_breakout_control': False, 'beats_buy_and_hold': False, 'beats_daily_dca': True, 'beats_random_timing_control': True, 'survives_doubled_cost': True, 'survives_best_trade_exclusion': True, 'survives_1bar_delay': True, 'concentration_ok': False, 'has_holdout_trades': True, 'monte_carlo_significant': False, 'deflated_sharpe_passes': False}
- Verdict: **REJECTED**

Partition breakdown:
| asset | partition | n_trades | mean_trade_return_pct |
| --- | --- | --- | --- |
| BTC | development_pre_2024 | 4 | 2.0178 |
| BTC | validation_2024 | 4 | 12.7362 |
| BTC | test_2025_onward | 2 | 1.9726 |

### ETH
- Combined breakout+depth signals: **35** raw / **17** executed trades
- Filtered final capital: **$8,508.75**
- Unfiltered breakout control final: **$11,142.09**
- Buy-and-hold final: **$15,798.41**
- Daily DCA final: **$8,101.70**
- Random-timing control final: **$16,040.85** (17 trades)
- Doubled-cost final: **$8,294.05**
- 1-bar delayed final: **$7,874.96** (17 trades)
- Best-trade-exclusion final: **$6,493.95**
- Top single-trade % of total PnL: **-173.5835534193339**
- Walk-forward: {'first_half_sharpe': -1.3241400239897623, 'second_half_sharpe': 0.5633165215889132, 'n_first': 8, 'n_second': 9}
- Monte Carlo: {'observed_sharpe': -0.07358587584836628, 'null_sharpe_std': 1.1827176188849506, 'p_value': 0.944, 'n_trials': 2000}
- Deflated Sharpe: {'sr_annualized': -0.08419522736277109, 'sr_per_bar': -0.017847196392729515, 'se_per_bar': 0.24564395335197992, 'n_obs': 17, 'n_trials': 97, 'dsr_stat': -2.592522379995563, 'dsr_p_value': 0.9952362508887698, 'passes_at_0.05': False}
- Gates: {'beats_unfiltered_breakout_control': False, 'beats_buy_and_hold': False, 'beats_daily_dca': True, 'beats_random_timing_control': False, 'survives_doubled_cost': False, 'survives_best_trade_exclusion': False, 'survives_1bar_delay': False, 'concentration_ok': False, 'has_holdout_trades': True, 'monte_carlo_significant': False, 'deflated_sharpe_passes': False}
- Verdict: **REJECTED**

Partition breakdown:
| asset | partition | n_trades | mean_trade_return_pct |
| --- | --- | --- | --- |
| ETH | development_pre_2024 | 4 | -4.6045 |
| ETH | validation_2024 | 6 | -1.1536 |
| ETH | test_2025_onward | 7 | 3.1120 |

### SOL
- Combined breakout+depth signals: **29** raw / **11** executed trades
- Filtered final capital: **$26,791.59**
- Unfiltered breakout control final: **$113,631.58**
- Buy-and-hold final: **$74,311.80**
- Daily DCA final: **$12,889.82**
- Random-timing control final: **$15,517.98** (11 trades)
- Doubled-cost final: **$26,352.18**
- 1-bar delayed final: **$25,885.89** (11 trades)
- Best-trade-exclusion final: **$11,742.63**
- Top single-trade % of total PnL: **65.58813943552076**
- Walk-forward: {'first_half_sharpe': 0.8546769396714828, 'second_half_sharpe': 1.0238092338438924, 'n_first': 5, 'n_second': 6}
- Monte Carlo: {'observed_sharpe': 1.144619548910931, 'null_sharpe_std': 1.8800394950159682, 'p_value': 0.372, 'n_trials': 2000}
- Deflated Sharpe: {'sr_annualized': 1.505965572176149, 'sr_per_bar': 0.3451157792221281, 'se_per_bar': 0.207431301389569, 'n_obs': 11, 'n_trials': 97, 'dsr_stat': -0.8561082366572357, 'dsr_p_value': 0.8040310434476214, 'passes_at_0.05': False}
- Gates: {'beats_unfiltered_breakout_control': False, 'beats_buy_and_hold': False, 'beats_daily_dca': True, 'beats_random_timing_control': True, 'survives_doubled_cost': True, 'survives_best_trade_exclusion': True, 'survives_1bar_delay': True, 'concentration_ok': False, 'has_holdout_trades': True, 'monte_carlo_significant': False, 'deflated_sharpe_passes': False}
- Verdict: **REJECTED**

Partition breakdown:
| asset | partition | n_trades | mean_trade_return_pct |
| --- | --- | --- | --- |
| SOL | development_pre_2024 | 5 | 23.6925 |
| SOL | validation_2024 | 5 | 6.4061 |
| SOL | test_2025_onward | 1 | 8.0164 |

### XRP
- Combined breakout+depth signals: **20** raw / **8** executed trades
- Filtered final capital: **$39,245.79**
- Unfiltered breakout control final: **$35,018.17**
- Buy-and-hold final: **$31,410.54**
- Daily DCA final: **$13,482.49**
- Random-timing control final: **$7,230.07** (8 trades)
- Doubled-cost final: **$38,776.60**
- 1-bar delayed final: **$31,374.13** (8 trades)
- Best-trade-exclusion final: **$9,876.02**
- Top single-trade % of total PnL: **108.09635227574152**
- Walk-forward: {'first_half_sharpe': 1.1846437327961188, 'second_half_sharpe': 0.9346706593066085, 'n_first': 4, 'n_second': 4}
- Monte Carlo: {'observed_sharpe': 1.0005276396202052, 'null_sharpe_std': 7.801876298791931, 'p_value': 0.393, 'n_trials': 2000}
- Deflated Sharpe: {'sr_annualized': 1.5023346901305072, 'sr_per_bar': 0.35373993937000864, 'se_per_bar': 0.2409727315557977, 'n_obs': 8, 'n_trials': 97, 'dsr_stat': -1.051900970332237, 'dsr_p_value': 0.8535775066514331, 'passes_at_0.05': False}
- Gates: {'beats_unfiltered_breakout_control': True, 'beats_buy_and_hold': True, 'beats_daily_dca': True, 'beats_random_timing_control': True, 'survives_doubled_cost': True, 'survives_best_trade_exclusion': False, 'survives_1bar_delay': True, 'concentration_ok': False, 'has_holdout_trades': True, 'monte_carlo_significant': False, 'deflated_sharpe_passes': False}
- Verdict: **REJECTED**

Partition breakdown:
| asset | partition | n_trades | mean_trade_return_pct |
| --- | --- | --- | --- |
| XRP | development_pre_2024 | 3 | 1.2301 |
| XRP | validation_2024 | 4 | 76.4735 |
| XRP | test_2025_onward | 1 | -6.5847 |

## Summary table
| asset | trades | filtered_final | unfiltered_control_final | buy_hold_final | dca_final | random_final | top_trade_pct | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BTC | 10 | 16445.3667 | 34302.1118 | 38484.6177 | 12457.9343 | 16000.7228 | 59.6143 | REJECTED |
| ETH | 17 | 8508.7533 | 11142.0904 | 15798.4120 | 8101.6962 | 16040.8485 | -173.5836 | REJECTED |
| SOL | 11 | 26791.5901 | 113631.5774 | 74311.8021 | 12889.8151 | 15517.9822 | 65.5881 | REJECTED |
| XRP | 8 | 39245.7886 | 35018.1723 | 31410.5413 | 13482.4852 | 7230.0719 | 108.0964 | REJECTED |

## Overall verdict
0/4 assets cleared every gate.
**REJECTED** -- no asset cleared every gate.