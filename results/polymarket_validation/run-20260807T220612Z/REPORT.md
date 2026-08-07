# Polymarket + Crypto Strategy Validation

This report backtests ten strategy ideas using real Binance OHLCV plus public Polymarket trade data reconstructed into hourly YES-probability series.

## Universe and evidence boundary

- BTC/ETH/SOL hourly spot data source: Binance public OHLCV pinned in this repo through 2026-07-28T00:00:00Z.
- Polymarket data source: public Gamma search metadata + public Data API trade history reconstructed to hourly last-trade probability.
- Crypto trade costs: 0.15% one-way (repo standard fee + slippage).
- Polymarket-native strategy cost assumption: 0.20% one-way slippage/fee proxy.
- Curated event markets fetched: 9.
- Broader resolved/flow universe discovered from query basket: 31 markets.

## Strategy summary

                   strategy    status  trade_count  win_rate  avg_return  median_return  ending_equity  total_return  max_drawdown                                                                                                                                                                                                    note
   cross_venue_disagreement   blocked            0       NaN         NaN            NaN   10000.000000      0.000000      0.000000 Kalshi historical API is publicly reachable, but matching and fetching the exact comparable market tickers/candles was not completed in this run. This strategy remains blocked rather than fabricated.
             eth_etf_spread completed            1  1.000000    0.091543       0.091543   10915.429604      0.091543      0.000000                                                                                                                Long ETH / short BTC for 72h after large ETH ETF approval-odds shocks above a 60% level.
          trump_policy_beta completed            0       NaN         NaN            NaN   10000.000000      0.000000      0.000000                                                                    Long BTC after positive Trump-election odds shocks when the market is already above 50%, treating odds as a pro-crypto policy proxy.
wick_with_odds_confirmation completed            0       NaN         NaN            NaN   10000.000000      0.000000      0.000000                                                                                          Buy violent BTC wick flushes only when supportive ETF/election/reserve odds are not simultaneously collapsing.
      resolution_time_decay completed            0       NaN         NaN            NaN   10000.000000      0.000000      0.000000                                                                                                                    Fade late 24h-to-6h surges into the 85%-97% or 3%-15% zone, then hold to resolution.
bitcoin_etf_flow_prediction completed            0       NaN         NaN            NaN   10000.000000      0.000000      0.000000                                                                                              Trade BTC for 24h when pre-resolution ETF-flow odds are strongly skewed toward positive or negative flows.
     favorite_longshot_bias completed           26  0.076923   -0.000114      -0.002999    9951.653458     -0.004835     -0.063941                                                                                             On resolved markets, buy YES favorites >65% or buy NO against YES longshots <35% one day before resolution.
         fed_cut_macro_beta completed            9  0.333333   -0.008180      -0.009012    9255.089378     -0.074491     -0.095166                                                                                                            Trade ETH on front-end Fed-cut probability shocks, using ETH as the higher-beta macro proxy.
         odds_shock_catchup completed           81  0.370370   -0.008784      -0.005094    4755.524900     -0.524448     -0.541826                                                                                              Buy/short BTC when a major Polymarket event reprices >8 points in 24h and BTC has not already overreacted.
   crypto_specific_lead_lag completed           54  0.407407   -0.014321      -0.009591    4072.481630     -0.592752     -0.606480                                                                                       Trade the coin directly when a crypto-specific Polymarket market reprices sharply and spot has not yet caught up.

## Strategy notes

### odds_shock_catchup
Buy/short BTC when a major Polymarket event reprices >8 points in 24h and BTC has not already overreacted.

### eth_etf_spread
Long ETH / short BTC for 72h after large ETH ETF approval-odds shocks above a 60% level.

### trump_policy_beta
Long BTC after positive Trump-election odds shocks when the market is already above 50%, treating odds as a pro-crypto policy proxy.

### fed_cut_macro_beta
Trade ETH on front-end Fed-cut probability shocks, using ETH as the higher-beta macro proxy.

### wick_with_odds_confirmation
Buy violent BTC wick flushes only when supportive ETF/election/reserve odds are not simultaneously collapsing.

### crypto_specific_lead_lag
Trade the coin directly when a crypto-specific Polymarket market reprices sharply and spot has not yet caught up.

### cross_venue_disagreement
Kalshi historical API is publicly reachable, but matching and fetching the exact comparable market tickers/candles was not completed in this run. This strategy remains blocked rather than fabricated.

### favorite_longshot_bias
On resolved markets, buy YES favorites >65% or buy NO against YES longshots <35% one day before resolution.

### resolution_time_decay
Fade late 24h-to-6h surges into the 85%-97% or 3%-15% zone, then hold to resolution.

### bitcoin_etf_flow_prediction
Trade BTC for 24h when pre-resolution ETF-flow odds are strongly skewed toward positive or negative flows.

## Top trade samples

                strategy                     market_slug       asset               signal_time                entry_time                 exit_time  direction  entry_price  exit_price  return_pct                  note
      odds_shock_catchup  bitcoin-etf-approved-by-jan-15         BTC 2023-12-02 19:00:00+00:00 2023-12-02 20:00:00+00:00 2023-12-03 20:00:00+00:00         -1    39419.990    39565.99   -0.006704 24h odds delta=-0.130
crypto_specific_lead_lag  bitcoin-etf-approved-by-jan-15         BTC 2023-12-02 19:00:00+00:00 2023-12-02 20:00:00+00:00 2023-12-04 20:00:00+00:00         -1    39419.990    41987.29   -0.068127 24h odds delta=-0.130
      odds_shock_catchup  bitcoin-etf-approved-by-jan-15         BTC 2023-12-04 21:00:00+00:00 2023-12-04 22:00:00+00:00 2023-12-05 22:00:00+00:00          1    42039.990    43891.10    0.041032  24h odds delta=0.090
      odds_shock_catchup  bitcoin-etf-approved-by-jan-15         BTC 2023-12-10 19:00:00+00:00 2023-12-10 20:00:00+00:00 2023-12-11 20:00:00+00:00          1    43797.100    40779.99   -0.071888  24h odds delta=0.080
crypto_specific_lead_lag  bitcoin-etf-approved-by-jan-15         BTC 2023-12-10 19:00:00+00:00 2023-12-10 20:00:00+00:00 2023-12-12 20:00:00+00:00          1    43797.100    41137.99   -0.063714  24h odds delta=0.080
      odds_shock_catchup  bitcoin-etf-approved-by-jan-15         BTC 2023-12-20 02:00:00+00:00 2023-12-20 03:00:00+00:00 2023-12-21 03:00:00+00:00          1    42428.010    43389.94    0.019672  24h odds delta=0.097
crypto_specific_lead_lag  bitcoin-etf-approved-by-jan-15         BTC 2023-12-20 02:00:00+00:00 2023-12-20 03:00:00+00:00 2023-12-22 03:00:00+00:00          1    42428.010    43966.07    0.033251  24h odds delta=0.097
      odds_shock_catchup  bitcoin-etf-approved-by-jan-15         BTC 2023-12-26 18:00:00+00:00 2023-12-26 19:00:00+00:00 2023-12-27 19:00:00+00:00         -1    42163.530    43183.99   -0.027202 24h odds delta=-0.080
crypto_specific_lead_lag  bitcoin-etf-approved-by-jan-15         BTC 2023-12-26 18:00:00+00:00 2023-12-26 19:00:00+00:00 2023-12-28 19:00:00+00:00         -1    42163.530    42480.00   -0.010506 24h odds delta=-0.080
crypto_specific_lead_lag  bitcoin-etf-approved-by-jan-15         BTC 2024-01-02 09:00:00+00:00 2024-01-02 10:00:00+00:00 2024-01-04 10:00:00+00:00          1    45673.480    43007.73   -0.061365  24h odds delta=0.148
      odds_shock_catchup  bitcoin-etf-approved-by-jan-15         BTC 2024-01-02 09:00:00+00:00 2024-01-02 10:00:00+00:00 2024-01-03 10:00:00+00:00          1    45673.480    45344.66   -0.010199  24h odds delta=0.148
      odds_shock_catchup  bitcoin-etf-approved-by-jan-15         BTC 2024-01-04 04:00:00+00:00 2024-01-04 05:00:00+00:00 2024-01-05 05:00:00+00:00         -1    43149.990    43589.87   -0.013194 24h odds delta=-0.085
crypto_specific_lead_lag  bitcoin-etf-approved-by-jan-15         BTC 2024-01-06 11:00:00+00:00 2024-01-06 12:00:00+00:00 2024-01-08 12:00:00+00:00          1    43671.970    44636.00    0.019074  24h odds delta=0.090
      odds_shock_catchup  bitcoin-etf-approved-by-jan-15         BTC 2024-01-06 11:00:00+00:00 2024-01-06 12:00:00+00:00 2024-01-07 12:00:00+00:00          1    43671.970    44061.10    0.005910  24h odds delta=0.090
      odds_shock_catchup  bitcoin-etf-approved-by-jan-15         BTC 2024-01-08 15:00:00+00:00 2024-01-08 16:00:00+00:00 2024-01-09 16:00:00+00:00          1    44963.040    46868.08    0.039369  24h odds delta=0.082
crypto_specific_lead_lag  bitcoin-etf-approved-by-jan-15         BTC 2024-01-09 18:00:00+00:00 2024-01-09 19:00:00+00:00 2024-01-11 19:00:00+00:00         -1    46640.500    46610.00   -0.002346 24h odds delta=-0.140
      odds_shock_catchup  bitcoin-etf-approved-by-jan-15         BTC 2024-01-10 17:00:00+00:00 2024-01-10 18:00:00+00:00 2024-01-11 18:00:00+00:00          1    46401.880    46497.14   -0.000947  24h odds delta=0.090
crypto_specific_lead_lag ethereum-etf-approved-by-may-31         ETH 2024-01-11 00:00:00+00:00 2024-01-11 01:00:00+00:00 2024-01-13 01:00:00+00:00         -1     2606.420     2517.45    0.031135 24h odds delta=-0.090
      odds_shock_catchup ethereum-etf-approved-by-may-31         ETH 2024-01-12 07:00:00+00:00 2024-01-12 08:00:00+00:00 2024-01-13 08:00:00+00:00         -1    46008.190    43102.97    0.060146 24h odds delta=-0.152
  favorite_longshot_bias  bitcoin-etf-approved-by-jan-15 POLY_NATIVE 2024-01-14 00:00:00+00:00 2024-01-14 00:00:00+00:00 2024-01-15 00:00:00+00:00          1        0.999        1.00   -0.002999    buy_yes_24h_before
crypto_specific_lead_lag ethereum-etf-approved-by-may-31         ETH 2024-01-16 20:00:00+00:00 2024-01-16 21:00:00+00:00 2024-01-18 21:00:00+00:00         -1     2586.870     2446.44    0.051286 24h odds delta=-0.100
      odds_shock_catchup ethereum-etf-approved-by-may-31         ETH 2024-01-16 20:00:00+00:00 2024-01-16 21:00:00+00:00 2024-01-17 21:00:00+00:00         -1    43200.010    42722.90    0.008044 24h odds delta=-0.100
      odds_shock_catchup ethereum-etf-approved-by-may-31         ETH 2024-01-18 15:00:00+00:00 2024-01-18 16:00:00+00:00 2024-01-19 16:00:00+00:00          1    42619.310    40894.71   -0.043465  24h odds delta=0.080
      fed_cut_macro_beta         fed-rate-cut-by-june-12         ETH 2024-02-13 13:00:00+00:00 2024-02-13 14:00:00+00:00 2024-02-15 14:00:00+00:00         -1     2643.610     2810.52   -0.066137 24h odds delta=-0.099
      odds_shock_catchup ethereum-etf-approved-by-may-31         ETH 2024-02-19 23:00:00+00:00 2024-02-20 00:00:00+00:00 2024-02-21 00:00:00+00:00          1    51774.740    52258.82    0.006350  24h odds delta=0.080
crypto_specific_lead_lag ethereum-etf-approved-by-may-31         ETH 2024-02-19 23:00:00+00:00 2024-02-20 00:00:00+00:00 2024-02-22 00:00:00+00:00          1     2944.800     2967.91    0.004848  24h odds delta=0.080
      fed_cut_macro_beta         fed-rate-cut-by-june-12         ETH 2024-03-05 12:00:00+00:00 2024-03-05 13:00:00+00:00 2024-03-07 13:00:00+00:00         -1     3759.000     3781.60   -0.009012 24h odds delta=-0.170
      fed_cut_macro_beta         fed-rate-cut-by-june-12         ETH 2024-03-08 14:00:00+00:00 2024-03-08 15:00:00+00:00 2024-03-10 15:00:00+00:00          1     3973.420     3896.84   -0.022273  24h odds delta=0.085
crypto_specific_lead_lag ethereum-etf-approved-by-may-31         ETH 2024-03-10 19:00:00+00:00 2024-03-10 20:00:00+00:00 2024-03-12 20:00:00+00:00         -1     3898.010     3980.23   -0.024093 24h odds delta=-0.100
      odds_shock_catchup ethereum-etf-approved-by-may-31         ETH 2024-03-10 19:00:00+00:00 2024-03-10 20:00:00+00:00 2024-03-11 20:00:00+00:00         -1    69400.190    71970.00   -0.040029 24h odds delta=-0.100
      fed_cut_macro_beta         fed-rate-cut-by-june-12         ETH 2024-03-12 13:00:00+00:00 2024-03-12 14:00:00+00:00 2024-03-14 14:00:00+00:00         -1     4024.600     3878.68    0.033257 24h odds delta=-0.088
crypto_specific_lead_lag ethereum-etf-approved-by-may-31         ETH 2024-03-15 16:00:00+00:00 2024-03-15 17:00:00+00:00 2024-03-17 17:00:00+00:00         -1     3683.930     3611.36    0.016699 24h odds delta=-0.099
      odds_shock_catchup ethereum-etf-approved-by-may-31         ETH 2024-03-15 16:00:00+00:00 2024-03-15 17:00:00+00:00 2024-03-16 17:00:00+00:00         -1    67893.780    68187.05   -0.007320 24h odds delta=-0.099
      odds_shock_catchup ethereum-etf-approved-by-may-31         ETH 2024-03-17 10:00:00+00:00 2024-03-17 11:00:00+00:00 2024-03-18 11:00:00+00:00          1    67169.120    68129.99    0.011305  24h odds delta=0.117
      odds_shock_catchup ethereum-etf-approved-by-may-31         ETH 2024-03-19 22:00:00+00:00 2024-03-19 23:00:00+00:00 2024-03-20 23:00:00+00:00         -1    62633.970    67681.94   -0.083595 24h odds delta=-0.089
crypto_specific_lead_lag ethereum-etf-approved-by-may-31         ETH 2024-03-19 22:00:00+00:00 2024-03-19 23:00:00+00:00 2024-03-21 23:00:00+00:00         -1     3211.280     3483.19   -0.087673 24h odds delta=-0.089
      fed_cut_macro_beta         fed-rate-cut-by-june-12         ETH 2024-03-20 19:00:00+00:00 2024-03-20 20:00:00+00:00 2024-03-22 20:00:00+00:00          1     3379.000     3340.46   -0.014406  24h odds delta=0.111
      odds_shock_catchup ethereum-etf-approved-by-may-31         ETH 2024-03-26 06:00:00+00:00 2024-03-26 07:00:00+00:00 2024-03-27 07:00:00+00:00          1    70616.010    70310.00   -0.007333  24h odds delta=0.090
crypto_specific_lead_lag ethereum-etf-approved-by-may-31         ETH 2024-03-26 06:00:00+00:00 2024-03-26 07:00:00+00:00 2024-03-28 07:00:00+00:00          1     3649.450     3574.39   -0.023567  24h odds delta=0.090
      fed_cut_macro_beta         fed-rate-cut-by-june-12         ETH 2024-03-28 13:00:00+00:00 2024-03-28 14:00:00+00:00 2024-03-30 14:00:00+00:00         -1     3582.600     3543.47    0.007922 24h odds delta=-0.081

## Curated market metadata

                                                              slug          family asset       volume             end_date                                                 question
will-trump-create-a-national-bitcoin-reserve-in-his-first-100-days bitcoin_reserve   BTC 2.332435e+07 2025-04-29T12:00:00Z     Will Trump create Bitcoin reserve in first 100 days?
                                    bitcoin-etf-approved-by-jan-15         btc_etf   BTC 1.262242e+07 2024-01-15T00:00:00Z                          Bitcoin ETF approved by Jan 15?
                                   ethereum-etf-approved-by-may-31         eth_etf   ETH 1.322651e+07 2024-05-31T12:00:00Z                         Ethereum ETF approved by May 31?
                                           fed-rate-cut-by-june-12         fed_cut   ETH 1.253484e+06 2024-06-12T00:00:00Z                                 Fed rate cut by June 12?
                                          fed-rate-cut-by-march-20         fed_cut   ETH 1.907759e+06 2024-03-20T00:00:00Z                                Fed rate cut by March 20?
                                             fed-rate-cut-by-may-1         fed_cut   ETH 1.608416e+06 2024-05-01T00:00:00Z                                   Fed rate cut by May 1?
                                       us-recession-by-end-of-2026       recession   BTC 1.698307e+06 2027-01-31T00:00:00Z                             US recession by end of 2026?
                               solana-etf-approved-by-july-31-2025         sol_etf   SOL 1.882647e+06 2025-07-31T12:00:00Z                          Solana ETF approved by July 31?
           will-donald-trump-win-the-2024-us-presidential-election  trump_election   BTC 1.531479e+09 2024-11-05T12:00:00Z Will Donald Trump win the 2024 US Presidential Election?

