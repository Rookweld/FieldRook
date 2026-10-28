# Collector sample packages (synthetic, deterministic)

Built by [build_samples.py](build_samples.py) (`python collector/samples/build_samples.py`
from the repo root). All contents are synthetic fixture data — no real host,
user, or secret. Timestamps, package IDs, hostname hash (`FIELD-PC-042`),
and durations are pinned so rebuilds are byte-identical except ZIP metadata.

| package | evidence | files | notes |
|---|---|---|---|
| `sample_basic.zip` | fixture collection, all categories + `wuauserv` service detail | `notes/collector-note.md` | no chunks |
| `sample_chunked.zip` | fixture collection + ~30KB app-log doc | `notes/case-note.txt`, `files/app-summary.log` | doc pre-chunked per D3a (`chunk_seq`/`chunk_of` + `refresh_of` chain) |

Both packages pass `archive.extract_and_verify` (structure + `file_hashes` +
manifest schema). The chunked log reassembles via `chunker.unchunk_data`.
