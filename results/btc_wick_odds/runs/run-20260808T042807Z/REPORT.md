# BTC wick flush + supportive odds validation

## Primary preregistered rule

- Timeframe: `1h` BTC spot bars from Binance.
- Wick detector: `low / rolling_max(high.shift(1), 48h) - 1 <= -10%`.
- Rolling peak excludes the current bar via `shift(1)` to avoid lookahead.
- Support filter: mean YES odds across BTC ETF, ETH ETF, Trump election, and Bitcoin reserve markets must have a 24h delta of at least `-2` points.
- Confirmation: first close within the next `24h` that is at least `3%` above the event low.
- Entry: next hourly open after confirmation; exit `72h` later at the next hourly open.
- Cooldown: no overlapping positions; wait until `48h` after exit before accepting a new event.

## Result table

                        strategy  final_usd_value  final_cash_usd  final_btc_units  final_btc_equivalent  final_btc_close  event_count  gross_spent_usd  total_costs_usd  unused_cash_usd  total_return_on_committed_capital  max_drawdown avg_trade_return win_rate
                   daily_btc_dca      9245.229236        0.000000              0.0              0.145010         63755.86         1031     10000.000000        15.000000         0.000000                          -0.075477      0.443181             <NA>     <NA>
           weekly_monday_btc_dca      9212.221661        0.000000              0.0              0.144492         63755.86          148     10000.000000        15.000000         0.000000                          -0.078778      0.442100             <NA>     <NA>
btc_wick_supportive_odds_rebound     10846.028662    10846.028662              0.0              0.170118         63755.86            6     19059.923136        57.179769     10846.028662                           0.084603      0.070057         0.048067      1.0

## Partition summary

              partition                     start                       end  final_usd_value  final_btc_equivalent  events  costs_usd  max_drawdown  avg_trade_return                         strategy
development_2023q4_2024 2023-10-01 00:00:00+00:00 2024-12-31 23:00:00+00:00      7642.782561              0.081675       0   0.000000      0.273583               NaN                    daily_btc_dca
    holdout_2025_onward 2025-01-01 00:00:00+00:00 2026-07-27 23:00:00+00:00      9245.229236              0.145010       0   0.000000      0.443181               NaN                    daily_btc_dca
development_2023q4_2024 2023-10-01 00:00:00+00:00 2024-12-31 23:00:00+00:00      7583.296200              0.081039       0   0.000000      0.271127               NaN            weekly_monday_btc_dca
    holdout_2025_onward 2025-01-01 00:00:00+00:00 2026-07-27 23:00:00+00:00      9212.221661              0.144492       0   0.000000      0.442100               NaN            weekly_monday_btc_dca
development_2023q4_2024 2023-10-01 00:00:00+00:00 2024-12-31 23:00:00+00:00      4828.301073              0.051598       4  23.042829      0.070057          0.052214 btc_wick_supportive_odds_rebound
    holdout_2025_onward 2025-01-01 00:00:00+00:00 2026-07-27 23:00:00+00:00     10846.028662              0.170118       2  34.136941      0.067186          0.039774 btc_wick_supportive_odds_rebound

## Sensitivity checks

                     strategy  final_usd_value  final_cash_usd  final_btc_units  final_btc_equivalent  final_btc_close  event_count  gross_spent_usd  total_costs_usd  unused_cash_usd  total_return_on_committed_capital  max_drawdown  avg_trade_return  win_rate  excess_btc_vs_daily  excess_btc_vs_weekly                check
 btc_wick_w48_dd10_sf8_b3_h48     10389.642597    10389.642597              0.0              0.162960         63755.86            7     20354.077165        61.062231     10389.642597                           0.038964      0.069944          0.022178  0.714286             0.017950              0.018468    nearby_parameters
 btc_wick_w48_dd10_sf8_b3_h72     10846.028662    10846.028662              0.0              0.170118         63755.86            6     19059.923136        57.179769     10846.028662                           0.084603      0.070057          0.048067  1.000000             0.025108              0.025626    nearby_parameters
 btc_wick_w48_dd10_sf8_b3_h96     10796.616326    10796.616326              0.0              0.169343         63755.86            6     18289.031149        54.867093     10796.616326                           0.079662      0.085793          0.033454  0.666667             0.024333              0.024851    nearby_parameters
 btc_wick_w48_dd10_sf8_b5_h48     10001.656239    10001.656239              0.0              0.156874         63755.86            6     17351.786916        52.055361     10001.656239                           0.000166      0.072407         -0.001228  0.333333             0.011864              0.012382    nearby_parameters
 btc_wick_w48_dd10_sf8_b5_h72     10233.767473    10233.767473              0.0              0.160515         63755.86            5     15774.154078        47.322462     10233.767473                           0.023377      0.072481          0.011412  0.600000             0.015505              0.016023    nearby_parameters
 btc_wick_w48_dd10_sf8_b5_h96     10333.682313    10333.682313              0.0              0.162082         63755.86            5     15572.572221        46.717717     10333.682313                           0.033368      0.085299          0.007155  0.600000             0.017072              0.017590    nearby_parameters
btc_wick_w48_dd10_sf10_b3_h48     10085.501109    10085.501109              0.0              0.158189         63755.86            4      7204.458791        21.613376     10085.501109                           0.008550      0.074012          0.011846  0.750000             0.013180              0.013697    nearby_parameters
btc_wick_w48_dd10_sf10_b3_h72     10190.279060    10190.279060              0.0              0.159833         63755.86            4      7281.061770        21.843185     10190.279060                           0.019028      0.096468          0.025428  0.750000             0.014823              0.015341    nearby_parameters
btc_wick_w48_dd10_sf10_b3_h96     10224.632804    10224.632804              0.0              0.160372         63755.86            4      7415.027044        22.245081     10224.632804                           0.022463      0.096484          0.031280  0.500000             0.015362              0.015879    nearby_parameters
btc_wick_w48_dd10_sf10_b5_h48      9942.565817     9942.565817              0.0              0.155947         63755.86            3      5088.962971        15.266889      9942.565817                          -0.005743      0.076710         -0.009568  0.333333             0.010938              0.011455    nearby_parameters
btc_wick_w48_dd10_sf10_b5_h72      9932.538314     9932.538314              0.0              0.155790         63755.86            3      5098.355651        15.295067      9932.538314                          -0.006746      0.096287         -0.010696  0.333333             0.010780              0.011298    nearby_parameters
btc_wick_w48_dd10_sf10_b5_h96      9985.826385     9985.826385              0.0              0.156626         63755.86            3      5243.141542        15.729425      9985.826385                          -0.001417      0.096378          0.002218  0.333333             0.011616              0.012134    nearby_parameters
 btc_wick_w48_dd12_sf8_b3_h48     10242.169493    10242.169493              0.0              0.160647         63755.86            3      5773.223676        17.319671     10242.169493                           0.024217      0.051731          0.045708  1.000000             0.015637              0.016155    nearby_parameters
 btc_wick_w48_dd12_sf8_b3_h72     10377.564209    10377.564209              0.0              0.162770         63755.86            3      5873.337677        17.620013     10377.564209                           0.037756      0.067511          0.068180  1.000000             0.017760              0.018278    nearby_parameters
 btc_wick_w48_dd12_sf8_b3_h96     10273.140808    10273.140808              0.0              0.161132         63755.86            3      5748.344931        17.245035     10273.140808                           0.027314      0.086431          0.051501  0.666667             0.016123              0.016640    nearby_parameters
 btc_wick_w48_dd12_sf8_b5_h48     10059.319191    10059.319191              0.0              0.157779         63755.86            2      3514.982501        10.544948     10059.319191                           0.005932      0.051714          0.021937  0.500000             0.012769              0.013287    nearby_parameters
 btc_wick_w48_dd12_sf8_b5_h72     10091.757361    10091.757361              0.0              0.158288         63755.86            2      3537.673638        10.613021     10091.757361                           0.009176      0.067260          0.031897  0.500000             0.013278              0.013795    nearby_parameters
 btc_wick_w48_dd12_sf8_b5_h96     10030.638266    10030.638266              0.0              0.157329         63755.86            2      3542.337272        10.627012     10030.638266                           0.003064      0.086054          0.017154  0.500000             0.012319              0.012837    nearby_parameters
btc_wick_w48_dd12_sf10_b3_h48     10101.100811    10101.100811              0.0              0.158434         63755.86            2      3981.137030        11.943411     10101.100811                           0.010110      0.051698          0.024402  1.000000             0.013424              0.013942    nearby_parameters
btc_wick_w48_dd12_sf10_b3_h72     10189.383382    10189.383382              0.0              0.159819         63755.86            2      4003.618548        12.010856     10189.383382                           0.018938      0.067060          0.045714  1.000000             0.014809              0.015327    nearby_parameters
btc_wick_w48_dd12_sf10_b3_h96     10111.223400    10111.223400              0.0              0.158593         63755.86            2      3921.864333        11.765593     10111.223400                           0.011122      0.085651          0.026665  0.500000             0.013583              0.014101    nearby_parameters
btc_wick_w48_dd12_sf10_b5_h48      9969.651679     9969.651679              0.0              0.156372         63755.86            1      1901.066925         5.703201      9969.651679                          -0.003035      0.051691         -0.015964  0.000000             0.011362              0.011880    nearby_parameters
btc_wick_w48_dd12_sf10_b5_h72      9979.189914     9979.189914              0.0              0.156522         63755.86            1      1901.066925         5.703201      9979.189914                          -0.002081      0.066946         -0.010947  0.000000             0.011512              0.012030    nearby_parameters
btc_wick_w48_dd12_sf10_b5_h96      9917.314397     9917.314397              0.0              0.155551         63755.86            1      1901.066925         5.703201      9917.314397                          -0.008269      0.085430         -0.043494  0.000000             0.010542              0.011059    nearby_parameters
 btc_wick_w72_dd10_sf8_b3_h48     10130.374789    10130.374789              0.0              0.158893         63755.86            8     21040.231165        63.120693     10130.374789                           0.013037      0.070991          0.012104  0.500000             0.013883              0.014401    nearby_parameters
 btc_wick_w72_dd10_sf8_b3_h72     10704.257518    10704.257518              0.0              0.167894         63755.86            7     19733.715113        59.201145     10704.257518                           0.070426      0.070995          0.033549  0.857143             0.022885              0.023402    nearby_parameters
 btc_wick_w72_dd10_sf8_b3_h96     10432.708952    10432.708952              0.0              0.163635         63755.86            7     18810.116749        56.430350     10432.708952                           0.043271      0.085614          0.015922  0.428571             0.018625              0.019143    nearby_parameters
 btc_wick_w72_dd10_sf8_b5_h48     10077.031959    10077.031959              0.0              0.158057         63755.86            7     19554.802801        58.664408     10077.031959                           0.007703      0.072407          0.004146  0.428571             0.013047              0.013564    nearby_parameters
 btc_wick_w72_dd10_sf8_b5_h72     10304.668998    10304.668998              0.0              0.161627         63755.86            6     18014.023525        54.042071     10304.668998                           0.030467      0.072481          0.014900  0.666667             0.016617              0.017135    nearby_parameters
 btc_wick_w72_dd10_sf8_b5_h96     10380.500706    10380.500706              0.0              0.162816         63755.86            6     17650.196223        52.950589     10380.500706                           0.038050      0.085299          0.009578  0.666667             0.017807              0.018324    nearby_parameters
btc_wick_w72_dd10_sf10_b3_h48      9879.816081     9879.816081              0.0              0.154963         63755.86            7     18871.958937        56.615877      9879.816081                          -0.012018      0.076796          0.001164  0.428571             0.009953              0.010471    nearby_parameters
btc_wick_w72_dd10_sf10_b3_h72     10211.159088    10211.159088              0.0              0.160160         63755.86            7     18813.974081        56.441922     10211.159088                           0.021116      0.096248          0.009702  0.571429             0.015150              0.015668    nearby_parameters
btc_wick_w72_dd10_sf10_b3_h96     10307.595534    10307.595534              0.0              0.161673         63755.86            7     19046.730245        57.140191     10307.595534                           0.030760      0.096292          0.015041  0.428571             0.016663              0.017181    nearby_parameters
btc_wick_w72_dd10_sf10_b5_h48     10133.096196    10133.096196              0.0              0.158936         63755.86            4     10414.651969        31.243956     10133.096196                           0.013310      0.076710          0.001768  0.500000             0.013926              0.014444    nearby_parameters
btc_wick_w72_dd10_sf10_b5_h72      9899.126523     9899.126523              0.0              0.155266         63755.86            4     10414.017146        31.242051      9899.126523                          -0.010087      0.096287         -0.009593  0.250000             0.010256              0.010774    nearby_parameters
btc_wick_w72_dd10_sf10_b5_h96     10201.977817    10201.977817              0.0              0.160016         63755.86            4     10612.091108        31.836273     10201.977817                           0.020198      0.096378          0.011729  0.500000             0.015006              0.015524    nearby_parameters
 btc_wick_w72_dd12_sf8_b3_h48     10058.770175    10058.770175              0.0              0.157770         63755.86            6     18002.939831        54.008819     10058.770175                           0.005877      0.074022          0.010434  0.500000             0.012760              0.013278    nearby_parameters
 btc_wick_w72_dd12_sf8_b3_h72     10610.805863    10610.805863              0.0              0.166429         63755.86            6     18460.774103        55.382322     10610.805863                           0.061081      0.096660          0.034017  0.833333             0.021419              0.021937    nearby_parameters
 btc_wick_w72_dd12_sf8_b3_h96     10599.606495    10599.606495              0.0              0.166253         63755.86            6     18468.324674        55.404974     10599.606495                           0.059961      0.096601          0.034756  0.500000             0.021243              0.021761    nearby_parameters
 btc_wick_w72_dd12_sf8_b5_h48     10022.688410    10022.688410              0.0              0.157204         63755.86            5     15730.422119        47.191266     10022.688410                           0.002269      0.076843          0.001133  0.400000             0.012194              0.012712    nearby_parameters
 btc_wick_w72_dd12_sf8_b5_h72     10185.070437    10185.070437              0.0              0.159751         63755.86            5     15652.293038        46.956879     10185.070437                           0.018507      0.096397          0.006132  0.600000             0.014741              0.015259    nearby_parameters
 btc_wick_w72_dd12_sf8_b5_h96     10442.313982    10442.313982              0.0              0.163786         63755.86            5     15899.792900        47.699379     10442.313982                           0.044231      0.096413          0.019251  0.600000             0.018776              0.019294    nearby_parameters
btc_wick_w72_dd12_sf10_b3_h48      9995.776886     9995.776886              0.0              0.156782         63755.86            3      5419.264045        16.257792      9995.776886                          -0.000422      0.073990         -0.004151  0.666667             0.011772              0.012290    nearby_parameters
btc_wick_w72_dd12_sf10_b3_h72     10073.950326    10073.950326              0.0              0.158008         63755.86            3      5429.994153        16.289982     10073.950326                           0.007395      0.096057          0.008991  0.666667             0.012998              0.013516    nearby_parameters
btc_wick_w72_dd12_sf10_b3_h96     10100.867037    10100.867037              0.0              0.158430         63755.86            3      5541.625521        16.624877     10100.867037                           0.010087      0.096057          0.015773  0.333333             0.013421              0.013938    nearby_parameters
btc_wick_w72_dd12_sf10_b5_h48      9892.491963     9892.491963              0.0              0.155162         63755.86            2      3461.840718        10.385522      9892.491963                          -0.010751      0.076511         -0.031900  0.000000             0.010152              0.010670    nearby_parameters
btc_wick_w72_dd12_sf10_b5_h72      9857.106002     9857.106002              0.0              0.154607         63755.86            2      3416.817084        10.250451      9857.106002                          -0.014289      0.095980         -0.043125  0.000000             0.009597              0.010115    nearby_parameters
btc_wick_w72_dd12_sf10_b5_h96      9884.262675     9884.262675              0.0              0.155033         63755.86            2      3505.697530        10.517093      9884.262675                          -0.011574      0.095980         -0.032287  0.000000             0.010023              0.010541    nearby_parameters
        btc_wick_doubled_cost     10784.778959    10784.778959              0.0              0.169157         63755.86            6     18963.440638       113.780644     10784.778959                           0.078478      0.070248          0.045067  1.000000             0.024148              0.024665 doubled_cost_primary

## Hostile checks

              check     value  secondary_value  passes           event_timestamp
primary_edge_vs_dca  0.025108         0.025626    True                       NaT
   holdout_positive  0.039774         2.000000    True                       NaT
 exclude_best_event -0.072595        -0.072077   False 2025-04-10 11:00:00+00:00

## Verdict

{
  "label": "promising_but_inconclusive",
  "reason": "Positive after-cost edge vs both DCA baselines survived nearby parameters and doubled costs, but the untouched holdout still has only a few events.",
  "primary_beats_both_dca": true,
  "nearby_parameter_pass_rate": 1.0,
  "doubled_cost_pass": true,
  "holdout_events": 2,
  "holdout_avg_trade_return": 0.03977414968776438
}

## Key takeaways

- Primary final BTC-equivalent: 0.17011815 vs daily DCA 0.14500987 and weekly DCA 0.14449216.
- Trade count: 6; average realized trade return: 4.81%.
- User-facing label: promising_but_inconclusive. Positive after-cost edge vs both DCA baselines survived nearby parameters and doubled costs, but the untouched holdout still has only a few events.

## Manifest

{
  "config": {
    "initial_capital": 10000.0,
    "one_way_cost": 0.0015,
    "contribution_hour_utc": 9,
    "sample_start": "2023-10-01T00:00:00Z",
    "holdout_start": "2025-01-01T00:00:00Z",
    "supportive_families": [
      "btc_etf",
      "eth_etf",
      "trump_election",
      "bitcoin_reserve"
    ],
    "primary_wick_window_hours": 48,
    "primary_drawdown_threshold": -0.1,
    "primary_support_delta_floor": -0.02,
    "primary_bounce_threshold": 0.03,
    "primary_bounce_window_hours": 24,
    "primary_hold_hours": 72,
    "primary_cooldown_hours": 48
  },
  "btc_data": {
    "path": "data/raw/BTC_1h.csv.gz",
    "kind": "spot_ohlcv",
    "coin": "BTC",
    "timeframe": "1h",
    "source": "Binance",
    "source_symbols": "BTCUSDT",
    "first_timestamp": "2018-01-01T00:00:00+00:00",
    "last_timestamp": "2026-07-27T23:00:00+00:00",
    "rows": 74998,
    "sha256": "8c594e1fb43e69088efd8d5980ae7e6db1e3d7dba7f943bde82ba54f008eeadc"
  },
  "sample_rows": 24744,
  "sample_start": "2023-10-01T00:00:00+00:00",
  "sample_end": "2026-07-27T23:00:00+00:00",
  "supportive_families": [
    "btc_etf",
    "eth_etf",
    "trump_election",
    "bitcoin_reserve"
  ]
}

