"""Merge translator output (app/i18n/ui/parts/<lang>_*.json) into app/i18n/ui/<lang>.json.

Existing entries are kept; part files win on conflict. Restart the server (or
wait for --reload) to pick up the new catalog.
"""
from __future__ import annotations

import json
from pathlib import Path

UI = Path(__file__).resolve().parents[1] / "app" / "i18n" / "ui"

for lang in ("hi", "ta"):
    target = UI / f"{lang}.json"
    merged = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
    for part in sorted((UI / "parts").glob(f"{lang}_*.json")):
        merged.update({k: v for k, v in json.loads(part.read_text(encoding="utf-8")).items() if v})
    target.write_text(
        json.dumps(dict(sorted(merged.items())), ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"{lang}: {len(merged)} strings")
