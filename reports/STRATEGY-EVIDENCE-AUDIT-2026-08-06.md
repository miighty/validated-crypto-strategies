# Strategy evidence audit — 6 August 2026

This is a decision report, not investment advice. “Historically profitable” means
the documented rule made money on its stated sample after its stated modelled
costs. It does not mean it is a live edge.

## New request: buy MSTR after an adverse BTC overnight move

**Rule tested:** BTC’s return from the previous US cash-equity close through the
completed 09:25 ET bar is below its expanding prior-only 95th-percentile
absolute-return threshold. Buy MSTR at the 09:30 opening print; sell at the
close of the 09:34, 09:39, or 09:44 bar. The result deducts 20 bps round trip;
50 bps is a hostile cost check.

**Window:** 4 August 2023 through 3 August 2026, the last finalized US session
in the local one-minute cache. The threshold is calculated from earlier data,
not re-fit inside this three-year window.

| Exit | Events | 20 bps mean event return | 20 bps compounded result | 50 bps compounded result |
|---|---:|---:|---:|---:|
| 5 minutes | 8 | +1.265% | +10.34% | +7.75% |
| 10 minutes | 8 | +2.159% | +18.02% | +15.28% |
| 15 minutes | 8 | +1.789% | +14.66% | +11.98% |

**Historical result:** profitable in this requested recent window, including the
50 bps cost stress. **Decision:** not approved. Eight events are far too few to
choose an exit after looking at the results, establish robustness, or fund a
strategy. This also conflicts with the 2021--2023 development-only result,
where every exit was negative. The result is a lead for a newly frozen
forward-only test, not a deployable rule.

Tesla is intentionally not shown: matching three-year, one-minute Nasdaq data
for TSLA is absent from the licensed local cache. A daily substitute would not
test an opening-to-5/10/15-minute rule.

## Completed historical studies

| Idea / rule | Historical outcome | Evidence decision |
|---|---|---|
| Weekly DCA benchmark | +2,289.63% in the repository’s ten-asset weekly DCA benchmark; max drawdown 78.33% | Completed benchmark, not the requested BTC-only Monday implementation and not a trading edge |
| Trend following | +283.00%; max drawdown 58.35% | Completed historical result; not promoted |
| Mean reversion | -98.90% | Rejected |
| Cross-sectional momentum | +15.05%; max drawdown 8.13% | Historically positive but not promoted as validated |
| Breakout baseline | +39.56%; max drawdown 61.25% | Historical baseline only |
| Frozen breakout candidate | +28.15% in the 2024--2026 forward window | Research candidate, not paper/live approved |
| Grid | -96.97% | Rejected |
| Funding arbitrage | -31.08% | Preliminary and negative; basis, borrow, collateral and liquidation are not modelled |
| Statistical arbitrage | -62.17% | Rejected |
| Contrarian | -58.25% | Rejected |
| RSI(14) oversold four-bar rule | -92.51% full sample; -48.00% forward | Rejected |
| BTC wild-move to crypto-equity gap | BTC leads the opening gap; 0.932 correlation across 25 primary overnight events | Descriptive relationship confirmed; no robust tradeable result |
| BTC-to-crypto-equity residual continuation | Long-only alternative +56.15% over five years | Rejected for deployment: later-event count, profit concentration, and threshold stability fail |
| MSTR opening fade, 2021--2023 selection | 5/10/15-minute variants -4.08%/-9.92%/-4.61% | Rejected under the original development-only protocol |

## Not completed or data-gated

| Idea | What is missing / why it was not accepted |
|---|---|
| BTC buy after a 30% 48-hour drawdown; short after a 30% 24-hour rise | No separately frozen implementation has yet been run |
| Strategy buy/sell events: are they priced in? | Needs a point-in-time event calendar and a frozen event-time rule |
| Large liquidations predict crypto equities | CoinGlass historical aggregate long/short liquidation entitlement. Existing account authentication is insufficient for this endpoint |
| Market making | Historical order-book, queue and fill data |
| Tesla opening fade | Licensed one-minute TSLA history for the requested window |

## What would change a decision

For the MSTR recent-window result, predeclare a single exit *before* collecting
new data, record executable quotes/fills, and observe materially more than
eight independent events. Require positive results after 50 bps costs, a
bootstrap lower bound above zero, and no event contributing more than 25% of
profits. Until then it is research, not a trade instruction.
