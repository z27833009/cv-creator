# PDF rendering troubleshooting

`build_cv.py` tries engines in this order (when `--engine auto`):

1. Microsoft Edge headless (Windows 11 built-in)
2. Google Chrome headless
3. Playwright chromium (auto-installs on first run via `uv run`)

If the PDF is wrong or missing, work through this list.

## Contents

- PDF file not produced
- Background colors missing
- Photo not appearing
- Fonts look wrong / characters missing
- Content overflows or wrong page count
- Engine-specific issues

## PDF file not produced

**Check the HTML first.** `build_cv.py` always writes the HTML (`--html-out` or next to the PDF path). Open it in a browser — if it renders correctly there, the bug is in the engine call, not the template.

If HTML is fine but PDF is missing:

- Re-run with `--engine playwright` to force the bundled renderer.
- Look at stderr — browser engines print the failure reason.
- On Windows, make sure the path does not contain characters that break the `file://` URI (spaces are OK when `as_uri()` is used, which it is).

## Background colors missing

Symptoms: sidebar appears white, gradients gone.

Fix (in the template, not the script):

```css
body {
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}
```

The browser call already passes `--no-pdf-header-footer` and `print_background=True` (Playwright).

## Photo not appearing

1. Check the YAML path: `personal.photo: ./photo.png` — must be **relative to the data.yaml file**, not the CWD.
2. Look at stderr for `warn: photo not found at ...`.
3. Verify the template references `personal.photo_data_uri`, not `personal.photo` directly.
4. If the photo file is correct but still blank, confirm the file extension maps to a common MIME type (png/jpg/webp).

## Fonts look wrong / characters missing

- CJK characters blank → the engine's default fallback lacks the glyphs. Edge on Windows 11 has full CJK coverage via Microsoft Yahei / Noto CJK. Playwright's bundled chromium on Windows typically does too, but may differ on Linux.
- Custom `@font-face` not loading → `build_cv.py` already calls `document.fonts.ready`; if you still see fallback, inline the font via base64 in the CSS.

## Content overflows or wrong page count

- Use `page-break-inside: avoid` on entries.
- Check for large margins in `@page`. The supplied templates use `margin: 0` and let the template control internal padding in mm.
- To squeeze one extra line in, lower `font-size` by 0.5pt on `.entry li` — don't force a second page.
- For debugging, render with `--no-pdf --html-out debug.html`, open in Chrome, and use the built-in print preview to see exactly how it paginates.

## Engine-specific issues

### Edge/Chrome headless fails silently

- Old Chrome versions (< 110) don't support `--headless=new`. Upgrade Chrome, or the script's fallback path will switch to Playwright.
- Some corporate-managed installs disable headless mode via policy. Force `--engine playwright`.

### Playwright: "Executable doesn't exist"

`build_cv.py` catches this and runs `playwright install chromium` automatically. If that fails (no network, firewall), install manually once:

```bash
uv run --with playwright playwright install chromium
```

### Paths with non-ASCII characters

All paths are passed via `Path.as_uri()`, which handles encoding. If you hit issues, move the data file to a plain-ASCII path for the test.

## Fast feedback loop

When iterating on a template or data, use:

```bash
uv run scripts/build_cv.py --data data.yaml --pattern modern-sidebar --no-pdf --html-out preview.html
```

Then refresh `preview.html` in the browser. Only run the full PDF once the HTML looks right.
