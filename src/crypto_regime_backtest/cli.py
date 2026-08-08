from __future__ import annotations

import argparse

from .alt_etf_btc_panel_validation import run_alt_etf_btc_panel_validation
from .breakout_compression_validation import run_breakout_compression_validation
from .btc_alt_response_validation import run_btc_alt_response_validation
from .btc_drawdown_dca_validation import run_btc_drawdown_dca_validation
from .btc_etf_validation import run_btc_etf_validation
from .btc_reserve_validation import run_btc_reserve_validation
from .btc_wick_odds_validation import run_btc_wick_odds_validation
from .config import Paths, project_root
from .data import collect
from .dominance_etf_validation import run_dominance_etf_validation
from .edge_validation import run_validation
from .eth_btc_etf_validation import run_eth_btc_etf_validation
from .xrp_btc_etf_validation import run_xrp_btc_etf_validation
from .pipeline import require_inputs, run
from .polymarket_crypto_validation import run_polymarket_crypto_validation
from .regimes import generate as generate_regimes
from .report import generate as generate_report
from .sol_eth_etf_validation import run_sol_eth_etf_validation
from .verify import verify


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Crypto regime strategy validation pipeline")
    subcommands = command.add_subparsers(dest="command", required=True)
    fetch = subcommands.add_parser("fetch", help="Fetch pinned public exchange data")
    fetch.add_argument(
        "--refresh", action="store_true", help="Replace the pinned local data snapshot"
    )
    subcommands.add_parser("run", help="Generate regimes and run all eligible backtests")
    subcommands.add_parser("report", help="Regenerate charts and REPORT.md from saved results")
    check = subcommands.add_parser("verify", help="Verify checksums, data invariants, and outputs")
    check.add_argument("--data-only", action="store_true", help="Do not require generated results")
    subcommands.add_parser(
        "validate-polymarket-crypto",
        help="Backtest Polymarket event-odds strategies against crypto price action",
    )
    subcommands.add_parser(
        "validate-eth-btc-etf",
        help="Validate ETH ETF odds -> ETH/BTC spread against ETH DCA baselines",
    )
    subcommands.add_parser(
        "validate-sol-eth-etf",
        help="Validate SOL ETF odds -> SOL/ETH spread against SOL DCA baselines",
    )
    subcommands.add_parser(
        "validate-xrp-btc-etf",
        help="Validate XRP ETF odds -> XRP/BTC spread against XRP DCA baselines",
    )
    subcommands.add_parser(
        "validate-alt-etf-btc-panel",
        help="Validate a pooled ETH/SOL/XRP ETF-odds family of long-alt/short-BTC spread trades",
    )
    subcommands.add_parser(
        "validate-breakout-compression",
        help="Validate a volatility-compression filter on accepted 4h crypto breakouts",
    )
    subcommands.add_parser(
        "validate-btc-alt-response",
        help="Validate BTC shock -> alt underreaction entries against alt DCA benchmarks",
    )
    subcommands.add_parser(
        "validate-btc-etf",
        help="Validate BTC ETF odds -> BTC swing entries against BTC DCA baselines",
    )
    subcommands.add_parser(
        "validate-btc-reserve",
        help="Validate Bitcoin-reserve odds -> BTC swing entries against BTC DCA baselines",
    )
    subcommands.add_parser(
        "validate-btc-wick-odds",
        help="Validate BTC wick flush rebound entries gated by supportive Polymarket odds against BTC DCA baselines",
    )
    subcommands.add_parser(
        "validate-btc-drawdown-dca",
        help="Validate BTC crash-buy reserve deployment against daily and weekly BTC DCA",
    )
    subcommands.add_parser(
        "validate-edge",
        help="Run the executable BTC extreme-move edge suite and fail-closed external studies",
    )
    subcommands.add_parser(
        "validate-dominance-etf",
        help="Fail-closed BTC dominance and ETF flow validation with point-in-time input checks",
    )
    subcommands.add_parser("all", help="Fetch if needed, run, report, and verify")
    return command


def main() -> None:
    args = parser().parse_args()
    paths = Paths(project_root())
    paths.create()
    if args.command == "fetch":
        collect(paths, refresh=args.refresh)
    elif args.command == "run":
        require_inputs(paths)
        generate_regimes(paths)
        run(paths)
    elif args.command == "report":
        generate_report(paths)
    elif args.command == "verify":
        verify(paths, require_results=not args.data_only)
    elif args.command == "validate-polymarket-crypto":
        require_inputs(paths)
        run_polymarket_crypto_validation(paths)
    elif args.command == "validate-eth-btc-etf":
        require_inputs(paths)
        run_eth_btc_etf_validation(paths)
    elif args.command == "validate-sol-eth-etf":
        require_inputs(paths)
        run_sol_eth_etf_validation(paths)
    elif args.command == "validate-xrp-btc-etf":
        require_inputs(paths)
        run_xrp_btc_etf_validation(paths)
    elif args.command == "validate-alt-etf-btc-panel":
        require_inputs(paths)
        run_alt_etf_btc_panel_validation(paths)
    elif args.command == "validate-breakout-compression":
        require_inputs(paths)
        run_breakout_compression_validation(paths)
    elif args.command == "validate-btc-alt-response":
        require_inputs(paths)
        run_btc_alt_response_validation(paths)
    elif args.command == "validate-btc-reserve":
        require_inputs(paths)
        run_btc_reserve_validation(paths)
    elif args.command == "validate-btc-wick-odds":
        require_inputs(paths)
        run_btc_wick_odds_validation(paths)
    elif args.command == "validate-btc-etf":
        require_inputs(paths)
        run_btc_etf_validation(paths)
    elif args.command == "validate-btc-drawdown-dca":
        require_inputs(paths)
        run_btc_drawdown_dca_validation(paths)
    elif args.command == "validate-edge":
        require_inputs(paths)
        run_validation(paths)
    elif args.command == "validate-dominance-etf":
        require_inputs(paths)
        run_dominance_etf_validation(paths)
    elif args.command == "all":
        try:
            require_inputs(paths)
        except FileNotFoundError:
            collect(paths)
        generate_regimes(paths)
        run(paths)
        generate_report(paths)
        verify(paths)


if __name__ == "__main__":
    main()
