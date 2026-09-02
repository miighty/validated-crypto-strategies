# Daily 20-Day-High Breakout + ATR Compression Filter -- Validation

## Primary rule
> LONG-ONLY: identical to the plain daily 20d-high/10d-low breakout system, but entry additionally requires the prior-only trailing 252-day percentile rank of ATR(14)/close to be <= 30 (compressed volatility regime) at the signal bar. Exit unchanged (10d-low break). 30bps round-trip cost.

## Data sources
- Real Binance spot 1d OHLCV (already cached, `data/raw/*_1d.csv.gz`). No synthetic data.

## Per-asset results
### BTC
- Trades: **34** (mean hold 21.4d)
- Compression-filtered primary final: **$59,579.33** (start $10,000)
- Unfiltered-breakout control final: **$86,092.91** (62 trades)
- Buy-and-hold final: **$46,414.40**
- Daily DCA final: **$40,001.66**
- Seeded random-timing control final: **$7,188.83** (34 trades)
- Doubled-cost final: **$56,610.46**
- 1-bar delayed-execution final: **$50,806.65** (34 trades)
- Best-trade-exclusion final: **$32,723.73**
- Top single-trade % of total PnL: **17.974529975445684**
- Walk-forward split: {'first_half_sharpe': 1.4002574709635127, 'second_half_sharpe': 1.2664041342693597, 'n_first': 17, 'n_second': 17}
- Monte Carlo bootstrap-null test: {'observed_sharpe': 1.8910846466522804, 'null_sharpe_std': 1.1686400808871344, 'p_value': 0.081, 'n_trials': 2000}
- Deflated Sharpe (n_trials=97): {'sr_annualized': 1.3404137542454428, 'sr_per_bar': 0.32431834128558734, 'se_per_bar': 0.12610933103204836, 'n_obs': 34, 'n_trials': 97, 'dsr_stat': 0.05185594326717324, 'dsr_p_value': 0.4793217395966124, 'passes_at_0.05': False}
- Gates: {'beats_cash': True, 'beats_bh': True, 'beats_dca': True, 'beats_random_control': True, 'beats_unfiltered_control': False, 'survives_doubled_cost': True, 'survives_best_trade_exclusion': True, 'survives_1bar_delay': True, 'concentration_ok': True, 'has_holdout_trades': True, 'monte_carlo_significant': False, 'deflated_sharpe_passes': False}
- Verdict: **REJECTED**

Partition breakdown:
| asset | partition | n_trades | mean_trade_return_pct |
| --- | --- | --- | --- |
| BTC | development_pre_2024 | 25 | 8.3012 |
| BTC | validation_2024 | 2 | 21.2488 |
| BTC | test_2025_onward | 7 | 0.8983 |

### ETH
- Trades: **39** (mean hold 19.0d)
- Compression-filtered primary final: **$65,184.56** (start $10,000)
- Unfiltered-breakout control final: **$177,993.91** (62 trades)
- Buy-and-hold final: **$25,779.94**
- Daily DCA final: **$34,806.07**
- Seeded random-timing control final: **$65,666.03** (39 trades)
- Doubled-cost final: **$61,472.55**
- 1-bar delayed-execution final: **$45,361.05** (39 trades)
- Best-trade-exclusion final: **$45,370.71**
- Top single-trade % of total PnL: **31.193234503816335**
- Walk-forward split: {'first_half_sharpe': 2.715168434200998, 'second_half_sharpe': 0.0678677008041414, 'n_first': 19, 'n_second': 20}
- Monte Carlo bootstrap-null test: {'observed_sharpe': 2.191330418081773, 'null_sharpe_std': 1.0408788763584786, 'p_value': 0.0355, 'n_trials': 2000}
- Deflated Sharpe (n_trials=97): {'sr_annualized': 1.53952632575479, 'sr_per_bar': 0.350893694224364, 'se_per_bar': 0.13998004042300655, 'n_obs': 39, 'n_trials': 97, 'dsr_stat': -0.01312673252823302, 'dsr_p_value': 0.5052366582195387, 'passes_at_0.05': False}
- Gates: {'beats_cash': True, 'beats_bh': True, 'beats_dca': True, 'beats_random_control': False, 'beats_unfiltered_control': False, 'survives_doubled_cost': True, 'survives_best_trade_exclusion': True, 'survives_1bar_delay': True, 'concentration_ok': False, 'has_holdout_trades': True, 'monte_carlo_significant': True, 'deflated_sharpe_passes': False}
- Verdict: **REJECTED**

Partition breakdown:
| asset | partition | n_trades | mean_trade_return_pct |
| --- | --- | --- | --- |
| ETH | development_pre_2024 | 30 | 7.4950 |
| ETH | validation_2024 | 2 | 2.2779 |
| ETH | test_2025_onward | 7 | 3.8599 |

### SOL
- Trades: **28** (mean hold 19.0d)
- Compression-filtered primary final: **$189,410.41** (start $10,000)
- Unfiltered-breakout control final: **$906,379.20** (43 trades)
- Buy-and-hold final: **$259,960.94**
- Daily DCA final: **$40,676.96**
- Seeded random-timing control final: **$29,067.84** (28 trades)
- Doubled-cost final: **$181,602.71**
- 1-bar delayed-execution final: **$105,140.30** (28 trades)
- Best-trade-exclusion final: **$42,027.92**
- Top single-trade % of total PnL: **20.593505536602365**
- Walk-forward split: {'first_half_sharpe': 0.7978179302611896, 'second_half_sharpe': 1.3278061312776068, 'n_first': 14, 'n_second': 14}
- Monte Carlo bootstrap-null test: {'observed_sharpe': 1.4826523303345593, 'null_sharpe_std': 3.034345743781679, 'p_value': 0.164, 'n_trials': 2000}
- Deflated Sharpe (n_trials=97): {'sr_annualized': 1.2273567977585018, 'sr_per_bar': 0.2801949533454022, 'se_per_bar': 0.11051037536969467, 'n_obs': 28, 'n_trials': 97, 'dsr_stat': 0.01559522384334252, 'dsr_p_value': 0.4937786580207293, 'passes_at_0.05': False}
- Gates: {'beats_cash': True, 'beats_bh': False, 'beats_dca': True, 'beats_random_control': True, 'beats_unfiltered_control': False, 'survives_doubled_cost': True, 'survives_best_trade_exclusion': True, 'survives_1bar_delay': True, 'concentration_ok': False, 'has_holdout_trades': True, 'monte_carlo_significant': False, 'deflated_sharpe_passes': False}
- Verdict: **REJECTED**

Partition breakdown:
| asset | partition | n_trades | mean_trade_return_pct |
| --- | --- | --- | --- |
| SOL | development_pre_2024 | 16 | 38.8317 |
| SOL | validation_2024 | 6 | 11.7293 |
| SOL | test_2025_onward | 6 | 3.1505 |

### XRP
- Trades: **39** (mean hold 16.2d)
- Compression-filtered primary final: **$53,654.53** (start $10,000)
- Unfiltered-breakout control final: **$83,657.29** (54 trades)
- Buy-and-hold final: **$21,290.06**
- Daily DCA final: **$22,418.70**
- Seeded random-timing control final: **$3,728.72** (39 trades)
- Doubled-cost final: **$50,599.10**
- 1-bar delayed-execution final: **$57,614.68** (39 trades)
- Best-trade-exclusion final: **$14,145.07**
- Top single-trade % of total PnL: **94.52021335582901**
- Walk-forward split: {'first_half_sharpe': 0.6718894506527626, 'second_half_sharpe': 1.0534688178931066, 'n_first': 19, 'n_second': 20}
- Monte Carlo bootstrap-null test: {'observed_sharpe': 1.2443441823494468, 'null_sharpe_std': 1.9020021594527912, 'p_value': 0.316, 'n_trials': 2000}
- Deflated Sharpe (n_trials=97): {'sr_annualized': 0.9467186973735505, 'sr_per_bar': 0.1992545366177176, 'se_per_bar': 0.09635185530916679, 'n_obs': 39, 'n_trials': 97, 'dsr_stat': -0.4518790629287923, 'dsr_p_value': 0.6743219458246499, 'passes_at_0.05': False}
- Gates: {'beats_cash': True, 'beats_bh': True, 'beats_dca': True, 'beats_random_control': True, 'beats_unfiltered_control': False, 'survives_doubled_cost': True, 'survives_best_trade_exclusion': True, 'survives_1bar_delay': True, 'concentration_ok': False, 'has_holdout_trades': True, 'monte_carlo_significant': False, 'deflated_sharpe_passes': False}
- Verdict: **REJECTED**

Partition breakdown:
| asset | partition | n_trades | mean_trade_return_pct |
| --- | --- | --- | --- |
| XRP | development_pre_2024 | 28 | 3.7816 |
| XRP | validation_2024 | 3 | 101.3559 |
| XRP | test_2025_onward | 8 | 0.7491 |

## Overall verdict
0/4 assets cleared every gate.

**REJECTED** -- no asset cleared every gate.