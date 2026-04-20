# Authoring a new pattern

Patterns are self-contained HTML/CSS templates. Each lives in `patterns/<name>/` and must contain:

```
patterns/
└── my-pattern/
    ├── template.html.j2     # Jinja2 template — REQUIRED
    ├── meta.yaml            # Metadata — recommended
    └── preview.png          # Optional thumbnail
```

## Contents

- Template context
- Template conventions
- meta.yaml fields
- Pagination and print CSS
- Workflow for creating a pattern

## Template context

`build_cv.py` renders `template.html.j2` with the parsed `data.yaml` as the Jinja2 context. All top-level keys are directly available:

| Available variable | Type    |
|--------------------|---------|
| `personal`         | mapping |
| `summary`          | string  |
| `work`             | list    |
| `projects`         | list    |
| `education`        | list    |
| `skills`           | list    |
| `languages`        | list    |
| `extras`           | list    |

See `references/data-schema.md` for the full shape of each.

**Photo**: if `personal.photo` was set, `build_cv.py` adds `personal.photo_data_uri` (base64 `data:image/...` URI). Your template references that field, never the raw path:

```jinja
{% if personal.photo_data_uri %}
  <img src="{{ personal.photo_data_uri }}" alt="{{ personal.name }}">
{% endif %}
```

## Template conventions

- **Autoescape is on** — strings are HTML-escaped automatically. Use `{{ x|safe }}` only for trusted HTML.
- **Strict undefined** — referencing a missing variable raises; guard optional fields with `{% if %}`.
- **Self-contained output** — do NOT reference external URLs for fonts or images unless you're OK waiting for network I/O during PDF render. Inline CSS + base64 images preferred.

## meta.yaml fields

```yaml
name: my-pattern                    # must match the directory name
description: One-line summary.      # shown in SKILL.md pattern picker
supports_photo: true                # whether template renders personal.photo_data_uri
pages: 1-2                          # expected page count (informational)
accent_color: "#56c8c4"             # primary accent (informational, for docs)
```

Only `description` is strictly required for a useful listing in `list_patterns.py`.

## Pagination and print CSS

For PDF output, always include:

```css
@page {
  size: A4;
  margin: 0;                        /* template handles padding internally */
}

@media print {
  body { background: #fff; }
  /* override any shadows or decorative margins that shouldn't print */
}
```

Use `page-break-inside: avoid` on entries (work/project/education blocks) so they don't split across pages:

```css
.entry { page-break-inside: avoid; }
```

`build_cv.py` calls the browser with `prefer_css_page_size: True`, so `@page` rules in the template take effect.

## Workflow for creating a pattern

1. **Copy an existing pattern** as a starting point:
   ```bash
   cp -r patterns/modern-sidebar patterns/my-pattern
   ```
2. **Rewrite `meta.yaml`** with the new name and description.
3. **Edit `template.html.j2`**. Keep it one file if possible — inline all CSS.
4. **Test** against `examples/data.example.yaml`:
   ```bash
   uv run scripts/build_cv.py \
     --data examples/data.example.yaml \
     --pattern my-pattern \
     --out /tmp/test.pdf \
     --html-out /tmp/test.html
   ```
5. **Inspect the HTML** first (fast feedback), then the PDF.
6. **Test edge cases**: missing `photo`, empty `projects`, long bullets, multi-page content.

## Common pitfalls

- **Grid/flex in print**: older rendering engines struggle. Always test the PDF, not just the HTML preview.
- **Background colors not printing**: include `-webkit-print-color-adjust: exact` and `print-color-adjust: exact` on `body`.
- **Fonts**: system fonts (`Segoe UI`, `Helvetica Neue`, `Arial`) render reliably. Custom `@font-face` requires `page.wait_for_load_state("networkidle")` which is already set in `build_cv.py`, but CJK fallbacks may differ between Edge and Chromium.
- **Content overflow**: if a section spills off the page, reduce `font-size`, shrink `line-height`, or trim bullets in `data.yaml` — don't patch the CSS for one person's content.
