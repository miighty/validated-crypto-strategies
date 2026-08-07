# ETH ETF Odds -> ETH/BTC Spread Validation

Run artifact: `results/eth_btc_etf/runs/run-20260807T230330Z/REPORT.md`

## Key findings

- **Primary rule tested:** ETH ETF YES odds jump by at least **10 points over 24h**, remain at or above **60%**, enter **long ETH / short BTC** at the next hourly open, hold **72h**, then exit.
- **Benchmarking method:** same $10,000 reserve released as equal daily contributions across the full sample, compared against **daily ETH DCA** and **weekly Monday ETH DCA**.
- **Sample window:** 2021-01-01 through 2026-07-27.

## Scoreboard

| Strategy | Final USD | Final ETH-equivalent | Events | Verdict |
|---|---:|---:|---:|---|
| Daily ETH DCA | 8602.24 | 4.54536410 | 2034 | Baseline |
| Weekly ETH DCA | 8595.67 | 4.54189136 | 291 | Baseline |
| ETH ETF odds -> ETH/BTC spread | 10556.28 | 5.57786601 | 1 | Inconclusive |

## Interpretation

### What is good
- The primary spread trade **beat both DCA baselines by a wide margin**.
- ETH-equivalent edge vs weekly DCA: **+1.03597464 ETH**.
- Max drawdown was tiny relative to DCA in this test: **3.06%** vs roughly **71%** for the passive ETH accumulation baselines.
- Nearby threshold / hold variants were also positive in this sample.
- The rule still stayed ahead even after **doubling trading costs**.

### Why it is still not validated
- The primary rule only generated **1 trade**.
- Hostile check `exclude_best_event` fails, because there is only one meaningful event driving the result.
- This means the signal is **promising** but still **not statistically serious enough** to approve as edge.

## Best honest conclusion

This is the **best candidate so far**, and it clearly deserves more work than the generic Polymarket strategies.

But the right label right now is:

> **Promising, but inconclusive due to tiny sample size.**

## Best next step

If continuing, prioritize one of these:

1. **Expand the event family** beyond just the May 2024 ETH ETF approval market:
   - more ETH ETF deadline markets
   - related SEC / approval / listing markets
   - analogous alt ETF approval markets for out-of-sample structure
2. **Test trade management variants** around the same signal:
   - 48h / 72h / 96h holds
   - scale-in by odds level
   - partial profit exits
3. **Cross-venue confirmation** if Kalshi or other comparable event odds can be aligned cleanly.

## Files

- `results/eth_btc_etf/runs/run-20260807T230330Z/REPORT.md`
- `results/eth_btc_etf/runs/run-20260807T230330Z/strategy_summary.csv`
- `results/eth_btc_etf/runs/run-20260807T230330Z/trade_log.csv`
- `results/eth_btc_etf/runs/run-20260807T230330Z/partition_summary.csv`
- `results/eth_btc_etf/runs/run-20260807T230330Z/sensitivity_checks.csv`
- `results/eth_btc_etf/runs/run-20260807T230330Z/hostile_checks.csv`
