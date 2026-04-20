#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pdfplumber>=0.11"]
# ///
"""Extract text from a PDF CV so Claude can transform it into data.yaml.

Usage:
    uv run ingest_pdf.py path/to/old-cv.pdf
    uv run ingest_pdf.py path/to/old-cv.pdf --out extracted.txt

Output goes to stdout (or --out); pages are separated by `\f` (form feed).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pdfplumber


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract text from a PDF.")
    parser.add_argument("pdf", type=Path, help="Input PDF path")
    parser.add_argument("--out", type=Path, help="Write to file instead of stdout")
    args = parser.parse_args()

    if not args.pdf.exists():
        print(f"error: file not found: {args.pdf}", file=sys.stderr)
        return 1

    chunks: list[str] = []
    with pdfplumber.open(str(args.pdf)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            chunks.append(f"--- page {i} ---\n{text}")

    output = "\n\f\n".join(chunks)
    if args.out:
        args.out.write_text(output, encoding="utf-8")
        print(f"wrote {len(output)} chars to {args.out}")
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
