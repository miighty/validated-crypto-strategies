"""Fetch real Binance USD-M futures open interest for the cross-sectional
OI-growth ranking study (EXP-2026-09-03-OIXSMOM-001).

Extends the existing 4-asset OI cache (BTC/ETH/SOL/XRP, already fetched for
prior single-asset OI studies) with 6 more liquid perpetuals: BNB, ADA,
DOGE, AVAX, LINK, ATOM. Uses the same real data.binance.vision daily-metrics
archive as every prior OI study in this repo -- no proxy/synthetic data.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crypto_regime_backtest.config import Paths, project_root
from crypto_regime_backtest.open_interest_data import collect_open_interest

ROOT = project_root()
PATHS = Paths(ROOT)

NEW_SYMBOLS = {
    "BNB": "BNBUSDT",
    "ADA": "ADAUSDT",
    "DOGE": "DOGEUSDT",
    "AVAX": "AVAXUSDT",
    "LINK": "LINKUSDT",
    "ATOM": "ATOMUSDT",
}

if __name__ == "__main__":
    collect_open_interest(PATHS, NEW_SYMBOLS, refresh=False)
    print("Done fetching new-coin OI data.")
