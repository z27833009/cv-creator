#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0"]
# ///
"""List available CV patterns with their metadata.

Invoked from SKILL.md via `!`…`` to inject the current pattern list
into the skill prompt at load time.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

PATTERNS_DIR = Path(__file__).resolve().parent.parent / "patterns"


def main() -> int:
    if not PATTERNS_DIR.exists():
        print("(no patterns directory)")
        return 0

    rows = []
    for entry in sorted(PATTERNS_DIR.iterdir()):
        if not entry.is_dir():
            continue
        meta_path = entry / "meta.yaml"
        template_path = entry / "template.html.j2"
        if not template_path.exists():
            continue
        meta = {}
        if meta_path.exists():
            try:
                meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError as e:
                print(f"warn: bad meta.yaml in {entry.name}: {e}", file=sys.stderr)
        rows.append(
            {
                "name": entry.name,
                "description": (meta.get("description") or "").strip(),
                "supports_photo": bool(meta.get("supports_photo", False)),
                "pages": meta.get("pages", "?"),
            }
        )

    if not rows:
        print("(no patterns found)")
        return 0

    print(f"{len(rows)} pattern(s) available:\n")
    for r in rows:
        photo = "photo" if r["supports_photo"] else "no-photo"
        print(f"- **{r['name']}** ({photo}, {r['pages']}pp): {r['description']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
