# Bitcoin NVT On-Chain Valuation Contrarian Validation

Run: `.venv/bin/python3 scripts/nvt_onchain_valuation_validation.py`
Artifact: `results/nvt_onchain_valuation/runs/run-20260903T003613Z/`

## Hypothesis

NVT (Network Value to Transactions ratio) = BTC market cap / a 90-day
trailing mean of real on-chain estimated USD transaction volume — the
closest on-chain analogue to a P/E ratio. The classic "NVT Signal" thesis
(Willy Woo) holds that deep NVT lows (network cheap vs its own recent
economic throughput) precede durable bottoms. Genuinely new data source and
mechanism for this repo — first use of real Blockchain.com market-cap and
on-chain transaction-value data; distinct from prior derivatives (DVOL,
funding, OI, CFTC-COT, top-trader/retail ratio), sentiment (FGI), price-only
(SMA200, breakout), stablecoin-flow, and miner-hashrate (Hash Ribbons)
studies.

## Design (frozen before inspection)

- Data: `api.blockchain.info/charts/market-cap` and
  `.../estimated-transaction-volume-usd`, both `sampled=false` for true daily
  granularity, real free public API, first use in this repo. Cached to
  `data/onchain_nvt/*.csv.gz`.
- Signal: `nvt = market_cap / rolling_90d_mean(tx_volume)`; z-score vs its
  own trailing 365-day prior-only history. Trigger: `z <= -1.25`.
- Execution: BTC spot only (on-chain tx-value data is BTC-specific; no proxy
  fabricated for ETH/SOL/XRP). Enter next-day 00:00 UTC open, 1-day
  publication lag, hold 30 days, non-overlapping.
- Costs: 30bps round trip (repo standard).
- Partitions: development 2018–2020, validation 2020–2023, test
  2023–2026-07-27.
- Benchmarks: buy-and-hold, daily DCA, seeded random-timing control
  (matching trade count/hold length).

## Result

| Gate | Result |
|---|---|
| Beats buy-and-hold | **FAIL** (2.20x vs 4.71x) |
| Beats DCA | **FAIL** (2.20x vs 4.00x) |
| Beats random-timing control | PASS (2.20x vs 1.80x) |
| Survives doubled cost | FAIL (2.09x, still < BH) |
| Survives best-trade exclusion | FAIL (1.46x) — one trade = 61.9% of total PnL |
| Concentration cap (<=20%) | FAIL (61.9%) |
| Test-partition beats BH | FAIL (1.20x vs 3.86x) |

Trigger fired on 9.9% of the full on-chain history (2011–2026). Only 17
non-overlapping trades fired in the tradeable BTC/USDT execution window
(2018-01-01 onward) — an adequate but not large sample. Full validation
ladder (walk-forward/MC/DSR) was not run: only 1/7 preregistered gates
passed, well below the program's Sharpe/gate threshold for promoting to
expensive validation compute (per the skill's exploratory-triage discipline).

## Verdict: REJECTED

Decisive rejection — the strategy loses outright to both required baselines
(buy-and-hold and DCA) on the full sample and in the untouched test
partition, and the modest apparent edge over cash is a concentration
artifact: a single trade supplies 62% of total realized PnL, far over this
program's 20% cap. Only the weakest gate (beating a seeded random-timing
control) passed.

## Interpretation

NVT extremes (as smoothed/thresholded here) do mark network-cheap regimes,
but crypto's realized forward returns following those regimes are
concentrated in a handful of episodes (mirroring this program's repeated
concentration-artifact finding across SMA200, DVOL, FGI, stablecoin-trend,
OI-trend, top-trader-trend, retail-ratio, Hash Ribbons, and order-book
studies) rather than a repeatable, diversified edge. Buy-and-hold captures
more of BTC's total return over this window than a 30-day-hold NVT-timing
overlay does.

Do not retest this exact threshold/hold/smoothing combination. If revisited,
would need either (a) a price-reclaim confirmation filter instead of
buying immediately on the NVT trigger, consistent with this program's other
"buy the panic" rejections, or (b) explicit position-sizing to cap
single-trade exposure — but per this program's established
concentration-fix pattern, expect further Sharpe compression, not rescue.

Items 1–3 in `docs/next_hypotheses.md` remain the highest-priority untested
single-asset/single-mechanism ideas requiring no new data. Items 6–8 remain
blocked on real liquidation/order-flow data this repo does not have.
