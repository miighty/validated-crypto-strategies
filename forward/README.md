# Forward paper observation

This directory is the append-only evidence area for
`EXP-2026-08-05-CROSS-ASSET-FORWARD-001`. The pre-registration is frozen in
`configs/cross_asset_forward.yaml` before the 5 August 2026 signal.

`cross_asset_paper_ledger.jsonl` is created by the first completed daily run. Each row
contains the hash of the previous row. `cross_asset_paper_status.json` is a replaceable
summary derived from that verified ledger. Neither artifact represents a broker order or
approval to trade.
