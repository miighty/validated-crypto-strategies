# Pre-FOMC-Announcement Drift Validation

EXP-2026-09-04-FOMCDRIFT-001

Run: `.venv/bin/python3 scripts/fomc_drift_validation.py`

## Hypothesis (preregistered)

The well-documented TradFi "pre-FOMC announcement drift" effect (Lucca &
Moench 2015, *Journal of Finance*): risk-asset returns are disproportionately
realized in the ~24h window immediately preceding a **scheduled** FOMC rate
decision, independent of whether the decision is hawkish or dovish (a
pre-announcement uncertainty-resolution premium, not a decision-content
signal). Genuinely new for this repo — first use of the FOMC's own scheduled
meeting calendar as a signal, distinct from `FED_HAWKISH_BTC_VALIDATION`
(a Polymarket rate-cut-odds momentum signal) and `DXY_TREND_REGIME_VALIDATION`
(a continuous FRED SMA-crossover regime).

## Data

- Real FOMC scheduled decision dates, 2018-01-31 through 2026-06-17 (68
  meetings used; sourced from the Federal Reserve's own public calendar
  pages — `federalreserve.gov/monetarypolicy/fomccalendars.htm` and
  `fomchistorical{2018,2019,2020}.htm`), cached to
  `data/macro_fomc/fomc_decision_dates.csv`. Decision time approximated as
  18:00 UTC (2:00pm ET) on the decision date.
- Real Binance spot hourly OHLCV, BTC/ETH/SOL/XRP (`data/raw/*_1h.csv.gz`,
  already cached).

## Design

- Entry 24h **before** each decision timestamp, exit 24h **after** (48h
  total hold, non-overlapping — meetings are >=5 weeks apart).
- Long-only, applied independently per asset.
- Costs: repo-standard 30bps round trip.
- Partitions: development (asset listing -> 2020-01-01), validation
  (2020-01-01 -> 2023-01-01), test (2023-01-01 -> end).
- Baselines: buy-and-hold, DCA, seeded random-timing control (same trade
  count/hold length/cost).

## Result

| Asset | Trades | Final ($10k start) | vs B&H | vs DCA | vs Random | Top-trade PnL share | Test partition (27 trades) |
| --- | ---: | ---: | --- | --- | --- | ---: | --- |
| BTC | 68 | $12,507 | loses ($47,125) | loses ($40,918) | beats ($6,410) | 59.6% | loses (0.81x vs B&H 3.86x) |
| ETH | 68 | $16,046 | loses ($26,010) | loses ($35,753) | beats ($14,626) | 40.2% | loses (0.88x vs B&H 1.58x) |
| SOL | 46 | $18,735 | loses ($251,398) | loses ($41,922) | beats ($9,743) | 36.5% | loses (0.90x vs B&H 7.43x) |
| XRP | 65 | $14,849 | **beats** ($11,550) | loses ($23,355) | beats ($10,984) | 52.7% | loses (0.65x vs B&H 3.15x) |

## Verdict: REJECTED (decisive)

- 0/4 assets clear the 20% concentration cap (36%-60% of total PnL sits in
  a single 48h window — a handful of FOMC dates, notably March 2020 and
  late-2022/2023 CPI-adjacent meetings, dominate).
- 0/4 assets pass the untouched 2023+ test partition — every asset's FOMC-
  window equity underperforms simple buy-and-hold by a wide margin in the
  most recent regime (0.65x-0.90x relative final vs 1.58x-7.43x B&H
  multiple over the same window).
- Only XRP beats buy-and-hold on the full sample; 0/4 beat DCA.
- All 4 assets beat the seeded random-timing control on raw final capital,
  which shows FOMC windows do carry *somewhat* elevated volatility/return
  versus arbitrary 48h windows — consistent with the TradFi literature's
  finding that pre-FOMC windows are unusual — but the effect is neither
  large enough nor stable enough to translate into a standalone tradeable
  edge on this cost model, sample size (46-68 trades), or test partition.

## Interpretation

The pre-FOMC drift literature documents a small, statistically-detectable
average excess return in equities around scheduled Fed decisions — it was
never claimed to be a large, robustly tradeable edge net of realistic
transaction costs, and crypto's own volatility and idiosyncratic BTC/ETH/
SOL/XRP-specific catalysts (which co-occur with many FOMC dates, e.g. March
2020 COVID crash, various 2022 macro selloffs) appear to swamp any genuine
drift signal. The "beats random control" result is real but too weak
relative to concentration risk and out-of-sample decay to promote.

## Follow-up

Do not retest this exact 24h/24h window definition without a new mechanism
(e.g. VIX-analogue crypto implied vol term-structure around FOMC, per DVOL
data already cached, or restricting to only "surprise" meetings via real
CME FedWatch-implied probability deltas). Items 1-3 in `next_hypotheses.md`
remain the highest-priority untested single-asset/single-mechanism ideas.
