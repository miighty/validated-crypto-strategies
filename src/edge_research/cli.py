from __future__ import annotations

import argparse

from .data import download


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Falsification-first crypto edge research")
    subcommands = command.add_subparsers(dest="command", required=True)
    fetch = subcommands.add_parser("download", help="Download finalized OHLCV to Parquet")
    fetch.add_argument("--config", default="configs/data.yaml")
    fetch.add_argument("--symbols", nargs="+", help="Override symbols, e.g. SOL ETC")
    run = subcommands.add_parser("run", help="Run one frozen experiment and generate its report")
    run.add_argument("--config", required=True)
    run.add_argument("--symbols", nargs="+", help="Run only these symbols from the snapshot")
    all_command = subcommands.add_parser("all", help="Download defaults and run both experiments")
    all_command.add_argument("--data-config", default="configs/data.yaml")
    all_command.add_argument("--symbols", nargs="+", help="Override the default symbol universe")
    subcommands.add_parser("verify", help="Verify data, reports, ledgers, registry, and Pine contracts")
    return command


def main() -> None:
    args = parser().parse_args()
    if args.command == "download":
        download(args.config, args.symbols)
    elif args.command == "run":
        from .experiments import run_experiment

        path = run_experiment(args.config, args.symbols)
        print(f"Generated {path}")
    elif args.command == "all":
        from .experiments import run_experiment

        download(args.data_config, args.symbols)
        for config in ("configs/rsi_mean_reversion.yaml", "configs/breakout_acceptance.yaml"):
            path = run_experiment(config, args.symbols)
            print(f"Generated {path}")
    elif args.command == "verify":
        from .verify import verify_repository

        verify_repository()


if __name__ == "__main__":
    main()
