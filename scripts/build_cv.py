#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "jinja2>=3.1",
#   "pyyaml>=6.0",
#   "playwright>=1.47",
# ]
# ///
"""Render a CV from data.yaml + a pattern directory to HTML and PDF.

Usage:
    uv run build_cv.py --data data.yaml --pattern modern-sidebar --out CV.pdf

PDF engine selection (in order):
  1. --engine flag (edge | chrome | playwright)
  2. Auto-detect Microsoft Edge on Windows
  3. Auto-detect Google Chrome
  4. Fallback: Playwright (auto-installs chromium on first run)

Photo handling:
  If personal.photo is set, it's embedded as a base64 data URI so the
  generated HTML is fully self-contained (no external file references).
"""
from __future__ import annotations

import argparse
import base64
import mimetypes
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
from jinja2 import ChainableUndefined, Environment, FileSystemLoader, select_autoescape

SKILL_DIR = Path(__file__).resolve().parent.parent
PATTERNS_DIR = SKILL_DIR / "patterns"


# ─── data loading ──────────────────────────────────────────────────────────

def load_data(data_path: Path) -> dict:
    if not data_path.exists():
        die(f"data file not found: {data_path}")
    raw = yaml.safe_load(data_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        die("data file must be a YAML mapping at the top level")
    if "personal" not in raw or not isinstance(raw["personal"], dict):
        die("data.personal is required")
    if "name" not in raw["personal"]:
        die("data.personal.name is required")
    return raw


def embed_photo(data: dict, data_dir: Path) -> None:
    """Resolve personal.photo (relative to data.yaml) into a data URI."""
    personal = data.get("personal", {})
    photo_ref = personal.get("photo")
    if not photo_ref:
        return
    photo_path = (data_dir / photo_ref).resolve() if not Path(photo_ref).is_absolute() else Path(photo_ref)
    if not photo_path.exists():
        print(f"warn: photo not found at {photo_path}, skipping", file=sys.stderr)
        return
    mime, _ = mimetypes.guess_type(photo_path.name)
    if not mime:
        mime = "image/png"
    encoded = base64.b64encode(photo_path.read_bytes()).decode("ascii")
    personal["photo_data_uri"] = f"data:{mime};base64,{encoded}"


# ─── rendering ─────────────────────────────────────────────────────────────

def flat_filter(value, sep: str = "\n") -> str:
    """Normalize any YAML-parsed value to a flat string.

    Defends against the common YAML gotcha where a bullet containing
    ": " is parsed as a mapping, e.g.
      - Owned CI/CD: GitHub Actions, Terraform
    becomes {'Owned CI/CD': 'GitHub Actions, Terraform'} instead of a
    plain string. Also handles accidental lists in string fields.
    """
    if value is None:
        return ""
    if isinstance(value, dict):
        return sep.join(f"{k}: {v}" for k, v in value.items())
    if isinstance(value, list):
        return sep.join(flat_filter(i, sep) for i in value)
    return str(value)


def render_html(data: dict, pattern_dir: Path) -> str:
    template_file = pattern_dir / "template.html.j2"
    if not template_file.exists():
        die(f"pattern missing template.html.j2: {pattern_dir}")
    env = Environment(
        loader=FileSystemLoader(str(pattern_dir)),
        autoescape=select_autoescape(["html", "xml"]),
        undefined=ChainableUndefined,
        trim_blocks=False,
        lstrip_blocks=False,
    )
    env.filters["flat"] = flat_filter
    env.filters["initials"] = lambda s: "".join(p[0] for p in (s or "").split()[:2]).upper()
    tmpl = env.get_template("template.html.j2")
    return tmpl.render(**data)


# ─── PDF engines ───────────────────────────────────────────────────────────

def find_browser() -> tuple[str, Path] | None:
    """Find a Chromium-family browser on the system. Return (kind, path) or None."""
    candidates: list[tuple[str, list[str]]] = []
    if platform.system() == "Windows":
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        local = os.environ.get("LOCALAPPDATA", "")
        candidates = [
            ("edge", [
                fr"{pf}\Microsoft\Edge\Application\msedge.exe",
                fr"{pf86}\Microsoft\Edge\Application\msedge.exe",
            ]),
            ("chrome", [
                fr"{pf}\Google\Chrome\Application\chrome.exe",
                fr"{pf86}\Google\Chrome\Application\chrome.exe",
                fr"{local}\Google\Chrome\Application\chrome.exe",
            ]),
        ]
    else:
        candidates = [
            ("chrome", ["google-chrome", "chromium", "chromium-browser"]),
            ("edge", ["microsoft-edge"]),
        ]

    for kind, paths in candidates:
        for p in paths:
            resolved = shutil.which(p) if not Path(p).is_absolute() else (p if Path(p).exists() else None)
            if resolved:
                return kind, Path(resolved)
    return None


def pdf_via_browser(html_path: Path, pdf_path: Path, browser_path: Path) -> None:
    """Use headless Chromium/Edge's --print-to-pdf to render."""
    # Use a fresh user data dir to avoid touching user's profile
    with tempfile.TemporaryDirectory() as user_data:
        cmd = [
            str(browser_path),
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            f"--user-data-dir={user_data}",
            "--no-pdf-header-footer",
            f"--print-to-pdf={pdf_path}",
            html_path.as_uri(),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0 or not pdf_path.exists():
            raise RuntimeError(
                f"browser PDF render failed (code {result.returncode}).\n"
                f"stderr: {result.stderr[:500]}"
            )


def pdf_via_playwright(html_path: Path, pdf_path: Path) -> None:
    """Use Playwright's chromium.page.pdf(). Installs chromium if missing."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        die("playwright not available. Re-run via `uv run build_cv.py`.")

    def _run():
        from playwright.sync_api import sync_playwright as _sp
        with _sp() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page()
                page.goto(html_path.as_uri(), wait_until="networkidle")
                # wait for any @font-face to finish loading
                page.evaluate("document.fonts && document.fonts.ready")
                page.pdf(
                    path=str(pdf_path),
                    format="A4",
                    print_background=True,
                    prefer_css_page_size=True,
                    margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
                )
            finally:
                browser.close()

    try:
        _run()
    except Exception as e:
        # Likely missing chromium; try installing once.
        if "Executable doesn't exist" in str(e) or "playwright install" in str(e):
            print("Playwright: installing chromium (first-time setup)...", file=sys.stderr)
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
            _run()
        else:
            raise


# ─── CLI ───────────────────────────────────────────────────────────────────

def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a CV PDF from data + pattern.")
    parser.add_argument("--data", required=True, type=Path, help="Path to data.yaml")
    parser.add_argument("--pattern", default="modern-sidebar", help="Pattern name under patterns/")
    parser.add_argument("--out", type=Path, help="Output PDF path (default: ./CV-<name>.pdf)")
    parser.add_argument("--html-out", type=Path, help="Also write rendered HTML to this path")
    parser.add_argument(
        "--engine",
        choices=["auto", "edge", "chrome", "playwright"],
        default="auto",
        help="PDF engine (default: auto — try Edge/Chrome then Playwright)",
    )
    parser.add_argument("--no-pdf", action="store_true", help="Render HTML only, skip PDF")
    args = parser.parse_args()

    data_path: Path = args.data.resolve()
    pattern_dir = PATTERNS_DIR / args.pattern
    if not pattern_dir.exists():
        die(f"unknown pattern: {args.pattern} (expected at {pattern_dir})")

    data = load_data(data_path)
    embed_photo(data, data_path.parent)
    html = render_html(data, pattern_dir)

    # Default output paths
    safe_name = (data["personal"]["name"] or "CV").replace(" ", "-").replace("/", "-")
    out_pdf: Path = args.out.resolve() if args.out else Path.cwd() / f"CV-{safe_name}.pdf"
    out_html: Path = args.html_out.resolve() if args.html_out else out_pdf.with_suffix(".html")

    out_html.write_text(html, encoding="utf-8")
    print(f"HTML: {out_html}")

    if args.no_pdf:
        return 0

    # Pick engine
    engine = args.engine
    if engine == "auto":
        detected = find_browser()
        if detected:
            kind, browser_path = detected
            try:
                pdf_via_browser(out_html, out_pdf, browser_path)
                print(f"PDF:  {out_pdf}  (engine: {kind} headless @ {browser_path})")
                return 0
            except Exception as e:
                print(f"warn: {kind} render failed, falling back to playwright: {e}", file=sys.stderr)
        pdf_via_playwright(out_html, out_pdf)
        print(f"PDF:  {out_pdf}  (engine: playwright)")
        return 0

    if engine in ("edge", "chrome"):
        detected = find_browser()
        if not detected:
            die(f"no {engine} / chromium-family browser found on PATH")
        _, browser_path = detected
        pdf_via_browser(out_html, out_pdf, browser_path)
        print(f"PDF:  {out_pdf}  (engine: {engine})")
        return 0

    if engine == "playwright":
        pdf_via_playwright(out_html, out_pdf)
        print(f"PDF:  {out_pdf}  (engine: playwright)")
        return 0

    die(f"unknown engine: {engine}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
