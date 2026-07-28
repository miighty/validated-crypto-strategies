from __future__ import annotations

import hashlib
import json

import pandas as pd

from .config import COINS, END_EXCLUSIVE, STRATEGIES, TIMEFRAMES, Paths
from .data import validate_ohlcv


def verify(paths: Paths, require_results: bool = True) -> None:
    manifest_path = paths.data / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("data/manifest.json is missing; run fetch")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("synthetic_data_used") is not False:
        raise ValueError("Manifest does not affirm synthetic_data_used=false")
    if manifest.get("window_end_exclusive") != END_EXCLUSIVE:
        raise ValueError("Committed data window differs from code configuration")
    files = manifest.get("files", [])
    expected = len(COINS) * (len(TIMEFRAMES) + 1)
    if len(files) != expected:
        raise ValueError(f"Expected {expected} manifest entries, found {len(files)}")
    for record in files:
        path = paths.root / record["path"]
        if not path.exists():
            raise FileNotFoundError(path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != record["sha256"]:
            raise ValueError(f"Checksum mismatch: {path}")
        frame = pd.read_csv(path, parse_dates=["timestamp"])
        if len(frame) != record["rows"]:
            raise ValueError(f"Row-count mismatch: {path}")
        if record["kind"] == "spot_ohlcv":
            validate_ohlcv(frame, record["coin"], record["timeframe"])
    if require_results:
        required = [
            paths.results / "all_metrics.csv",
            paths.results / "master_summary.csv",
            paths.results / "per_coin_summary.csv",
            paths.results / "validation_status.csv",
            paths.root / "REPORT.md",
        ]
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            raise FileNotFoundError(f"Missing result artifacts: {missing}")
        status = pd.read_csv(paths.results / "validation_status.csv")
        if set(status["strategy"]) != set(STRATEGIES):
            raise ValueError("Validation status does not cover all ten strategies")
    print(f"Verified {len(files)} checksummed real-data files and repository result contract.")
