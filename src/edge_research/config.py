from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_yaml(path: str | Path) -> dict[str, Any]:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = project_root() / candidate
    with candidate.open(encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise TypeError(f"Configuration must be a mapping: {candidate}")
    value["_config_path"] = str(candidate)
    return value


def resolve_from_root(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else project_root() / path


@dataclass(frozen=True)
class ExecutionConfig:
    initial_capital: float = 10_000.0
    fee_rate: float = 0.0005
    slippage_rate: float = 0.0005
    entry_delay_bars: int = 1
    sizing: str = "fixed_fraction"
    allocation_fraction: float = 1.0
    risk_fraction: float = 0.01
    max_allocation: float = 1.0

    @classmethod
    def from_mapping(cls, value: dict[str, Any], **overrides: Any) -> ExecutionConfig:
        fields = {
            "initial_capital": value.get("initial_capital", 10_000.0),
            "fee_rate": value.get("fee_rate", 0.0005),
            "slippage_rate": value.get("slippage_rate", 0.0005),
            "entry_delay_bars": value.get("entry_delay_bars", 1),
            "sizing": value.get("sizing", "fixed_fraction"),
            "allocation_fraction": value.get("allocation_fraction", 1.0),
            "risk_fraction": value.get("risk_fraction", 0.01),
            "max_allocation": value.get("max_allocation", 1.0),
        }
        fields.update(overrides)
        result = cls(**fields)
        if result.entry_delay_bars < 1:
            raise ValueError("Signals from completed candles require entry_delay_bars >= 1")
        if result.fee_rate < 0 or result.slippage_rate < 0:
            raise ValueError("Costs cannot be negative")
        if result.sizing not in {"fixed_fraction", "volatility_adjusted"}:
            raise ValueError(f"Unsupported sizing method: {result.sizing}")
        return result
