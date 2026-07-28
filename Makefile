.PHONY: setup fetch run report test lint verify

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
