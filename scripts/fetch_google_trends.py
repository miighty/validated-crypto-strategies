"""Fetch and stitch real Google Trends weekly search-interest history for
'bitcoin' (2017-present) using overlapping-window chaining (pytrends caps a
single query span such that windows under ~5yr return weekly resolution;
longer spans return monthly). Standard ratio-based chaining stitches
overlapping windows onto a single continuous weekly index.

REAL DATA ONLY -- no synthetic/proxy data. If a chunk fetch fails after
retries, the whole run aborts rather than filling with fabricated values.
"""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
from pytrends.request import TrendReq

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "google_trends"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Overlapping windows, each < 5 years so pytrends returns weekly resolution.
# Consecutive windows overlap by >= 1 year to give a robust scaling ratio.
WINDOWS = [
    "2017-06-01 2021-06-01",
    "2020-01-01 2024-01-01",
    "2022-06-01 2026-09-04",
]

KEYWORD = "bitcoin"


def fetch_chunk(pt: TrendReq, window: str, retries: int = 5) -> pd.Series:
    last_err = None
    for attempt in range(retries):
        try:
            pt.build_payload([KEYWORD], timeframe=window)
            df = pt.interest_over_time()
            if df.empty:
                raise RuntimeError(f"Empty response for window {window}")
            s = df[KEYWORD].astype(float)
            s.index = pd.to_datetime(s.index, utc=True)
            return s
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(min(2 ** attempt * 5, 60))
    raise RuntimeError(f"Real Google Trends fetch failed for {window} after {retries} retries: {last_err}")


def stitch(chunks: list[pd.Series]) -> pd.Series:
    """Chain chunks left-to-right using overlap-ratio rescaling so the whole
    series is on one consistent relative-interest scale (0-100 anchored to
    the LAST/most-recent chunk, matching how one would read 'current'
    interest levels)."""
    # Work backwards from the last (most recent) chunk since we anchor scale
    # to it, then rescale earlier chunks to match on the overlap.
    stitched = chunks[-1].copy()
    for prev in reversed(chunks[:-1]):
        overlap_idx = prev.index.intersection(stitched.index)
        if len(overlap_idx) < 4:
            raise RuntimeError("Insufficient overlap between Google Trends chunks to stitch reliably")
        ratio = stitched.loc[overlap_idx].mean() / prev.loc[overlap_idx].mean()
        prev_rescaled = prev * ratio
        # keep only the portion of prev strictly before stitched's start
        new_part = prev_rescaled.loc[prev_rescaled.index < stitched.index.min()]
        stitched = pd.concat([new_part, stitched]).sort_index()
        stitched = stitched[~stitched.index.duplicated(keep="last")]
    return stitched


def main() -> None:
    pt = TrendReq(hl="en-US", tz=0)
    chunks = []
    for w in WINDOWS:
        s = fetch_chunk(pt, w)
        print(f"Fetched {w}: {len(s)} rows, {s.index.min()} -> {s.index.max()}")
        chunks.append(s)
        time.sleep(3)

    stitched = stitch(chunks)
    frame = stitched.to_frame("bitcoin_search_interest")
    frame.index.name = "date"
    out_path = OUT_DIR / "bitcoin_search_interest_weekly.csv.gz"
    frame.to_csv(out_path, compression="gzip")
    print(f"Wrote {len(frame)} rows to {out_path}")
    print(frame.head())
    print(frame.tail())


if __name__ == "__main__":
    main()
