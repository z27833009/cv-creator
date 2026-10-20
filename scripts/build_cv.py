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
import re
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


# ─── PDF self-check ────────────────────────────────────────────────────────

def verify_pdf_text_layer(pdf_path: Path) -> tuple[bool, str, list[str]]:
    """Sanity-check that the produced PDF has a real text layer.

    Catches the common Windows trap where a user's default printer is
    "Microsoft Print to PDF", which silently rasterizes pages containing
    CSS gradients or embedded images into a single full-page JPEG —
    producing a PDF whose text cannot be selected or parsed by ATS.

    The detection signal is the presence of `/Type /Font` objects.
    Text-bearing PDFs always declare at least one font; a rasterized
    "page = full-bleed JPEG" PDF (the Microsoft Print to PDF failure mode)
    has none. Searching for content-stream operators like `Tj`/`TJ`
    directly is unreliable because streams are usually flate-compressed.

    Returns (ok, producer, warnings).
    """
    warnings: list[str] = []
    try:
        data = pdf_path.read_bytes()
    except OSError as e:
        return False, "(unreadable)", [f"cannot read produced PDF: {e}"]

    if not data.startswith(b"%PDF"):
        return False, "(not a PDF)", ["output file is not a valid PDF"]

    m = re.search(rb"/Producer\s*\(([^)]{0,200})\)", data)
    producer = m.group(1).decode("latin1", "replace") if m else "(unknown)"

    has_font = b"/Type /Font" in data or b"/Type/Font" in data
    is_print_to_pdf = "print to pdf" in producer.lower()

    if not has_font:
        warnings.append(
            "PDF has no font objects — text is not selectable. "
            "Most likely cause: a virtual printer like 'Microsoft Print to PDF' "
            "rasterized the page into a single image. "
            "See references/pdf-troubleshooting.md → 'PDF text not selectable'."
        )
        return False, producer, warnings

    if is_print_to_pdf:
        warnings.append(
            f"PDF Producer is '{producer}'. This virtual printer can rasterize "
            "complex layouts; verify text selection manually."
        )

    return True, producer, warnings


def count_pdf_pages(pdf_path: Path) -> int:
    try:
        data = pdf_path.read_bytes()
        content = data.decode("ascii", errors="replace")
        matches = re.findall(r"/Type\s*/Page\b", content)
        return len(matches)
    except Exception as e:
        print(f"warn: failed to count PDF pages: {e}", file=sys.stderr)
        return 0



# ─── CLI ───────────────────────────────────────────────────────────────────

def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def render_pdf(out_html: Path, out_pdf: Path, engine: str) -> str:
    """Render HTML → PDF using the chosen engine. Returns the engine label used."""
    if engine == "auto":
        detected = find_browser()
        if detected:
            kind, browser_path = detected
            try:
                pdf_via_browser(out_html, out_pdf, browser_path)
                return f"{kind} headless @ {browser_path}"
            except Exception as e:
                print(
                    f"warn: {kind} render failed, falling back to playwright: {e}",
                    file=sys.stderr,
                )
        pdf_via_playwright(out_html, out_pdf)
        return "playwright"

    if engine in ("edge", "chrome"):
        detected = find_browser()
        if not detected:
            die(f"no {engine} / chromium-family browser found on PATH")
        _, browser_path = detected
        pdf_via_browser(out_html, out_pdf, browser_path)
        return engine

    if engine == "playwright":
        pdf_via_playwright(out_html, out_pdf)
        return "playwright"

    die(f"unknown engine: {engine}")
    return engine


def report_pdf(out_pdf: Path, engine_label: str, strict: bool) -> int:
    """Print the PDF path + result of the text-layer self-check."""
    ok, producer, warnings = verify_pdf_text_layer(out_pdf)
    status = "text-layer: OK" if ok else "text-layer: FAILED"
    print(f"PDF:  {out_pdf}  (engine: {engine_label}, {status}, producer: {producer})")
    for w in warnings:
        print(f"warn: {w}", file=sys.stderr)
    if not ok and strict:
        return 2
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a CV PDF from data + pattern.")
    parser.add_argument("--data", type=Path, help="Path to data.yaml")
    parser.add_argument(
        "--from-html",
        type=Path,
        help="Skip templating and render this existing HTML file directly to PDF",
    )
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
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if the produced PDF lacks a selectable text layer",
    )
    parser.add_argument("--config", type=Path, help="Path to cv-config.yaml to build multiple targets")
    args = parser.parse_args()

    if not args.data and not args.from_html and not args.config:
        die("provide either --data <data.yaml>, --from-html <file.html>, or --config <cv-config.yaml>")
    
    provided_modes = sum(1 for x in [args.data, args.from_html, args.config] if x is not None)
    if provided_modes > 1:
        die("--data, --from-html, and --config are mutually exclusive")

    # ── Mode 1: Render configuration-driven targets ──
    if args.config:
        config_path = args.config.resolve()
        if not config_path.exists():
            die(f"config file not found: {config_path}")
        
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        
        targets = config.get("targets")
        if not targets or not isinstance(targets, list):
            die("config file must contain a 'targets' list")
            
        config_dir = config_path.parent
        has_errors = False
        
        for t in targets:
            name = t.get("name", "Unnamed Target")
            data_rel = t.get("data")
            pattern_name = t.get("pattern")
            from_html_rel = t.get("from_html")
            out_rel = t.get("out")
            max_pages = t.get("max_pages")
            
            if not out_rel:
                print(f"error: target '{name}' must specify 'out'", file=sys.stderr)
                has_errors = True
                continue
                
            out_pdf = (config_dir / out_rel).resolve()
            
            if from_html_rel:
                src_html = (config_dir / from_html_rel).resolve()
                if not src_html.exists():
                    print(f"error: HTML file not found for target '{name}': {src_html}", file=sys.stderr)
                    has_errors = True
                    continue
                print(f"\n--- Compiling HTML target: {name} ---")
                if args.no_pdf:
                    print(f"HTML: {src_html}")
                    continue
                engine_label = render_pdf(src_html, out_pdf, args.engine)
                report_status = report_pdf(out_pdf, engine_label, args.strict)
                if report_status != 0:
                    has_errors = True
            else:
                if not data_rel or not pattern_name:
                    print(f"error: target '{name}' must specify either 'from_html' or ('data' and 'pattern')", file=sys.stderr)
                    has_errors = True
                    continue
                data_path = (config_dir / data_rel).resolve()
                pattern_dir = PATTERNS_DIR / pattern_name
                out_html = out_pdf.with_suffix(".html")
                
                if not data_path.exists():
                    print(f"error: data file not found for target '{name}': {data_path}", file=sys.stderr)
                    has_errors = True
                    continue
                if not pattern_dir.exists():
                    print(f"error: pattern not found for target '{name}': {pattern_dir}", file=sys.stderr)
                    has_errors = True
                    continue
                    
                print(f"\n--- Building target: {name} ---")
                data_loaded = load_data(data_path)
                embed_photo(data_loaded, data_path.parent)
                html = render_html(data_loaded, pattern_dir)
                out_html.write_text(html, encoding="utf-8")
                print(f"HTML: {out_html}")
                if args.no_pdf:
                    continue
                engine_label = render_pdf(out_html, out_pdf, args.engine)
                report_status = report_pdf(out_pdf, engine_label, args.strict)
                if report_status != 0:
                    has_errors = True
            
            pages = count_pdf_pages(out_pdf)
            print(f"Pages: {pages}")
            if max_pages is not None:
                if pages > max_pages:
                    print(f"error: target '{name}' exceeded page budget: {pages} > {max_pages} pages!", file=sys.stderr)
                    has_errors = True
                else:
                    print(f"Page budget check: OK ({pages} <= {max_pages})")
                    
        if has_errors:
            die("one or more targets failed to build or violated page budgets")
            
        print("\nAll targets compiled successfully!")
        return 0

    # ── Mode 2: render an existing HTML file directly ──
    if args.from_html:
        src_html = args.from_html.resolve()
        if not src_html.exists():
            die(f"HTML file not found: {src_html}")
        out_pdf: Path = args.out.resolve() if args.out else src_html.with_suffix(".pdf")
        if args.no_pdf:
            print(f"HTML: {src_html}")
            return 0
        engine_label = render_pdf(src_html, out_pdf, args.engine)
        return report_pdf(out_pdf, engine_label, args.strict)

    # ── Mode 3: data + pattern → HTML → PDF ──
    data_path: Path = args.data.resolve()
    pattern_dir = PATTERNS_DIR / args.pattern
    if not pattern_dir.exists():
        die(f"unknown pattern: {args.pattern} (expected at {pattern_dir})")

    data = load_data(data_path)
    embed_photo(data, data_path.parent)
    html = render_html(data, pattern_dir)

    # Default output paths
    safe_name = (data["personal"]["name"] or "CV").replace(" ", "-").replace("/", "-")
    out_pdf = args.out.resolve() if args.out else Path.cwd() / f"CV-{safe_name}.pdf"
    out_html: Path = args.html_out.resolve() if args.html_out else out_pdf.with_suffix(".html")

    out_html.write_text(html, encoding="utf-8")
    print(f"HTML: {out_html}")

    if args.no_pdf:
        return 0

    engine_label = render_pdf(out_html, out_pdf, args.engine)
    return report_pdf(out_pdf, engine_label, args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
