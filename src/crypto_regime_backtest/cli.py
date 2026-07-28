from __future__ import annotations

import argparse

from .config import Paths, project_root
from .data import collect
from .pipeline import require_inputs, run
from .regimes import generate as generate_regimes
from .report import generate as generate_report
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
