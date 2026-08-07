# BTC-to-crypto-equity opening-gap strategy: five-year validation

**Experiment:** `EXP-2026-08-05-CROSS-ASSET-STRAT-001`  
**Parent:** `EXP-2026-08-04-CROSS-ASSET-001`  
**Formal verdict:** **REJECTED FOR DEPLOYMENT**  
**Best alternative:** **HISTORICALLY PROFITABLE PAPER-RESEARCH CANDIDATE**

## Answer

There are two distinct answers depending on whether the frozen selection rule is respected.

1. **The formally selected strategy did not profit.** Development data selected BTC-direction continuation. A hypothetical $10,000 fell to **$6,732.12**, a **-$3,267.88 (-32.68%)** five-year result after the declared 20 bps round-trip costs.
2. **A long-only residual-continuation alternative did profit historically.** A hypothetical $10,000 grew to **$15,614.52**, a **+$5,614.52 (+56.15%)** result, approximately **9.32% annualized**, with a **-5.66%** maximum drawdown.

The profitable alternative is not labelled validated. It was not selected by the frozen development ranking, its forward result contains only seven event dates, one date generated 55.2% of forward positive profits, and its forward bootstrap interval includes zero.

## Executable working rule

The cleanest implementable version is **long-only residual continuation**:

1. At 09:25 ET, calculate BTC's return from the prior US equity close using only completed five-minute candles.
2. Trade only when the absolute BTC move exceeds its expanding prior-sample 95th percentile after at least 60 observations.
3. Estimate each stock's expected opening response from its prior 60 sessions of BTC, SPY, and QQQ sensitivity, requiring 40 complete sessions.
4. Observe the stock's 09:35–09:39 opening gap. Define `residual gap = observed gap - expected factor gap`.
5. At 09:40–09:44, buy only eligible stocks with a positive residual gap. Leave the allocation for non-qualifying stocks in cash; do not short.
6. Equal-weight the eligible stock slots and exit during 15:55–15:59.
7. Charge 20 bps round trip per entered stock; the hostile cost test charges 50 bps.

The 09:40 entry is essential. An earlier draft used the 09:35–09:39 observation window as its assumed fill, which was same-window lookahead. Those preliminary results were withdrawn and every number in this report uses the corrected later entry.

## Chronological results

Each period below independently starts with $10,000 so its gain can be read directly. The full-five-year row compounds all 34 event returns in sequence.

| Window | Event dates | Ending equity | Net profit | Return | Win rate | Maximum drawdown | Mean-event 95% interval |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Development: Aug 2021–2023 | 18 | $11,351.19 | +$1,351.19 | +13.51% | 50.0% | -5.11% | -0.59% to +2.26% |
| Validation: 2024 | 9 | $11,806.94 | +$1,806.94 | +18.07% | 66.7% | -0.38% | -0.17% to +4.30% |
| Chronological holdout: 2025–Aug 2026 | 7 | $11,650.64 | +$1,650.64 | +16.51% | 57.1% | -2.83% | -0.55% to +5.62% |
| Full five years | 34 | **$15,614.52** | **+$5,614.52** | **+56.15%** | 55.9% | **-5.66%** | +0.21% to +2.64% |

The holdout is chronological, but not pristine independent evidence: the parent studies had already summarized 2024–2026 before this strategy specification was finalized. The five-year ordering prevents direct parameter fitting on later dates, but it cannot undo that prior researcher exposure.

## Hostile sensitivities for the long-only rule

| Specification | Full return | Ending equity | Maximum drawdown | Holdout return | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| Primary: 95th percentile, 20 bps | +56.15% | $15,614.52 | -5.66% | +16.51% | Fails concentration/uncertainty |
| At least 300 observed minutes | +51.97% | $15,196.97 | -6.50% | +17.03% | Directionally survives |
| 50 bps round trip | +48.33% | $14,832.55 | -6.22% | +14.82% | Directionally survives |
| 90th-percentile event threshold | +22.60% | $12,260.30 | -22.58% | +7.05% | Development lost 9.21% |

The 95th-percentile result survives higher costs and the liquid-session filter. It is not threshold-stable: admitting more 90th-percentile events creates a development loss and materially larger drawdown.

## Why validation failed

- The frozen development selector chose `btc_continuation`, not residual continuation; the selected rule subsequently lost 15.49% in validation and 23.70% in the chronological holdout.
- The profitable long-only alternative has only seven holdout events.
- One holdout event supplied 55.2% of its positive profits, breaching the frozen 25% limit.
- The holdout mean-event bootstrap interval is -0.55% to +5.62%, so uncertainty includes no edge.
- The 90th-percentile sensitivity lost money in development.
- XNAS.ITCH is Nasdaq venue data, not consolidated all-venue execution data, and the OHLCV price is a volume-weighted typical-price proxy rather than trade-by-trade VWAP.

## Data and costs

- Equity window: 5 August 2021 through 3 August 2026.
- Equity data: 12,410,872 Databento XNAS.ITCH one-minute source records across the original and extension jobs.
- Five-year processed panel: 24,543 usable stock-sessions, 23 point-in-time tickers, and 1,253 US sessions.
- BTC data: 525,506 Binance BTCUSDT five-minute bars. One signal date affected by an exchange data outage was excluded rather than filled from a stale price.
- Corporate actions adjusted once across the full sequence: CORZ, HIVE, HUT, IBKR, and MSTR.
- Additional Databento cost for the five-year extension: $3.084648.

## Decision

Do not treat the +56.15% curve as a validated live edge. The appropriate next use is forward-only paper observation of the exact long-only rule, with no threshold or timing changes, until the independent event count is materially larger and no event supplies more than 25% of profits. No TradingView or capital-deployment handoff is approved by this result.

