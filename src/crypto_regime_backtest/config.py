from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

START = "2018-01-01T00:00:00Z"
# Exclusive and deliberately pinned: every committed result uses the same finalized window.
END_EXCLUSIVE = "2026-07-28T00:00:00Z"
TIMEFRAMES = ("1d", "4h", "1h")
FEE_RATE = 0.001
SLIPPAGE_RATE = 0.0005
ONE_WAY_COST = FEE_RATE + SLIPPAGE_RATE
STARTING_CAPITAL = 10_000.0


@dataclass(frozen=True)
class SymbolSegment:
    symbol: str
    start: str = START
    end_exclusive: str = END_EXCLUSIVE


# MATIC was migrated to POL on Binance. The two exchange symbols are retained in provenance.
COINS: dict[str, tuple[SymbolSegment, ...]] = {
    "BTC": (SymbolSegment("BTCUSDT"),),
    "ETH": (SymbolSegment("ETHUSDT"),),
    "SOL": (SymbolSegment("SOLUSDT"),),
    "BNB": (SymbolSegment("BNBUSDT"),),
    "XRP": (SymbolSegment("XRPUSDT"),),
    "ADA": (SymbolSegment("ADAUSDT"),),
    "DOGE": (SymbolSegment("DOGEUSDT"),),
    "AVAX": (SymbolSegment("AVAXUSDT"),),
    "LINK": (SymbolSegment("LINKUSDT"),),
    "POL": (
        SymbolSegment("MATICUSDT", end_exclusive="2024-09-11T00:00:00Z"),
        SymbolSegment("POLUSDT", start="2024-09-13T00:00:00Z"),
    ),
}

STRATEGIES = (
    "trend_following",
    "mean_reversion",
    "momentum",
    "breakout",
    "grid",
    "dca",
    "funding_arbitrage",
    "statistical_arbitrage",
    "market_making",
    "contrarian",
)

PERIODS_PER_YEAR = {"1d": 365.25, "4h": 365.25 * 6, "1h": 365.25 * 24}


@dataclass(frozen=True)
class Paths:
    root: Path

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def raw(self) -> Path:
        return self.data / "raw"

    @property
    def funding(self) -> Path:
        return self.data / "funding"

    @property
    def regimes(self) -> Path:
        return self.root / "regimes"

    @property
    def results(self) -> Path:
        return self.root / "results"

    @property
    def metrics(self) -> Path:
        return self.results / "metrics"

    @property
    def trades(self) -> Path:
        return self.results / "trades"

    @property
    def charts(self) -> Path:
        return self.root / "charts"

    @property
    def returns(self) -> Path:
        return self.results / "returns"

    def create(self) -> None:
        for path in (
            self.raw,
            self.funding,
            self.regimes,
            self.metrics,
            self.trades,
            self.returns,
            self.charts,
        ):
            path.mkdir(parents=True, exist_ok=True)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]
