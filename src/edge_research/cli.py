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
    cross_asset = subcommands.add_parser(
        "cross-asset-run", help="Run completed studies 6 and 7 from cached Databento and BTC data"
    )
    cross_asset.add_argument(
        "--equity-root",
        default="data/cache/cross_asset/databento/XNAS-20260804-ED35KSK6WW",
    )
    cross_asset.add_argument(
        "--btc-path", default="data/cache/cross_asset/BTCUSDT_5m.parquet"
    )
    cross_asset.add_argument(
        "--output", default="data/cache/cross_asset/studies_6_7_results.json"
    )
    cross_strategy = subcommands.add_parser(
        "cross-asset-strategy", help="Run the frozen five-year studies 6 and 7 strategy suite"
    )
    cross_strategy.add_argument(
        "--equity-path", default="data/cache/cross_asset/equity_daily_5y.parquet"
    )
    cross_strategy.add_argument(
        "--btc-path", default="data/cache/cross_asset/BTCUSDT_5m.parquet"
    )
    cross_strategy.add_argument(
        "--output", default="data/cache/cross_asset/strategy_5y_results.json"
    )
    forward = subcommands.add_parser(
        "cross-asset-forward", help="Append finalized sessions to the locked paper-forward ledger"
    )
    forward.add_argument("--through", required=True, help="Finalized US session, YYYY-MM-DD")
    forward.add_argument("--config", default="configs/cross_asset_forward.yaml")
    forward.add_argument(
        "--equity-path", default="data/cache/cross_asset/equity_daily_forward.parquet"
    )
    forward.add_argument(
        "--btc-path", default="data/cache/cross_asset/BTCUSDT_5m.parquet"
    )
    forward.add_argument(
        "--ledger", default="forward/cross_asset_paper_ledger.jsonl"
    )
    forward.add_argument(
        "--status", default="forward/cross_asset_paper_status.json"
    )
    forward_panel = subcommands.add_parser(
        "cross-asset-forward-prepare",
        help="Combine frozen history with new licensed Databento DBN files",
    )
    forward_panel.add_argument(
        "--base", default="data/cache/cross_asset/equity_daily_5y.parquet"
    )
    forward_panel.add_argument(
        "--forward-roots", nargs="+", required=True, help="Folders containing new .dbn.zst files"
    )
    forward_panel.add_argument(
        "--output", default="data/cache/cross_asset/equity_daily_forward.parquet"
    )
    mstr_fade = subcommands.add_parser(
        "mstr-open-fade", help="Test the pre-registered MSTR BTC-down opening-fade hypothesis"
    )
    mstr_fade.add_argument(
        "--equity-root",
        default="data/cache/cross_asset",
    )
    mstr_fade.add_argument("--btc-path", default="data/cache/cross_asset/BTCUSDT_5m.parquet")
    mstr_fade.add_argument(
        "--output", default="reports/EXP-2026-08-05-MSTR-OPEN-FADE-001_summary.json"
    )
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
    elif args.command == "cross-asset-run":
        from .cross_asset_studies import prepare_inputs, run_studies, write_results

        inputs = prepare_inputs(args.equity_root, args.btc_path)
        path = write_results(run_studies(inputs), args.output)
        print(f"Generated {path}")
    elif args.command == "cross-asset-strategy":
        import pandas as pd

        from .cross_asset_strategy import run_validation_suite
        from .cross_asset_studies import StudyInputs, btc_event_returns, write_results

        equity = pd.read_parquet(args.equity_path)
        btc = pd.read_parquet(args.btc_path)
        events = btc_event_returns(btc, equity.index.get_level_values("session"))
        inputs = StudyInputs(equity, events)
        path = write_results(run_validation_suite(inputs), args.output)
        print(f"Generated {path}")
    elif args.command == "cross-asset-forward":
        from .cross_asset_forward import run_forward_update

        appended, status = run_forward_update(
            args.config,
            args.equity_path,
            args.btc_path,
            args.ledger,
            args.status,
            args.through,
        )
        print(
            f"Appended {appended} session(s); "
            f"events={status['new_event_sessions']}/"
            f"{status['minimum_required_event_sessions']}; "
            f"independent_review={status['ready_for_independent_review']}"
        )
    elif args.command == "cross-asset-forward-prepare":
        from .cross_asset_forward import prepare_forward_equity_panel

        path = prepare_forward_equity_panel(args.base, args.forward_roots, args.output)
        print(f"Generated {path}")
    elif args.command == "mstr-open-fade":
        import pandas as pd

        from .cross_asset_studies import btc_event_returns
        from .mstr_open_fade import (
            load_mstr_minutes,
            run_mstr_open_fade_validation,
            write_mstr_open_fade_results,
        )

        minute = load_mstr_minutes(args.equity_root)
        btc = pd.read_parquet(args.btc_path)
        sessions = pd.DatetimeIndex(minute.index.normalize().tz_localize(None).unique())
        result = run_mstr_open_fade_validation(minute, btc_event_returns(btc, sessions))
        path = write_mstr_open_fade_results(result, args.output)
        print(f"Generated {path}; selected={result['selected_horizon']}; passed={result['validation_passed']}")


if __name__ == "__main__":
    main()
