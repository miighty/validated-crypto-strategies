.PHONY: setup fetch run report test lint verify edge-download edge-rsi edge-breakout edge-all edge-verify

setup:
	uv sync --extra dev

fetch:
	uv run crypto-regime-backtest fetch

run:
	uv run crypto-regime-backtest run

report:
	uv run crypto-regime-backtest report

test:
	uv run pytest -q

lint:
	uv run ruff check .

verify: lint test
	uv run crypto-regime-backtest verify

edge-download:
	uv run edge-research download --config configs/data.yaml

edge-rsi:
	uv run edge-research run --config configs/rsi_mean_reversion.yaml

edge-breakout:
	uv run edge-research run --config configs/breakout_acceptance.yaml

edge-all:
	uv run edge-research all

edge-verify:
	uv run edge-research verify
