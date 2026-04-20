---
name: cv-creator
description: "Generates a printable PDF CV from raw material (markdown, PDF, plain text, optional photo) using a chosen HTML/CSS template. Use when the user wants to create, update, regenerate, or restyle their CV or resume, switch CV templates, or export a CV to PDF."
allowed-tools: Read Write Edit Glob Grep Bash
argument-hint: "[pattern-name]"
---

# CV Creator

Build a structured CV from raw input, render it through an HTML/CSS **pattern**, and produce a self-contained PDF. Content (`data.yaml`) is separated from presentation (patterns) so the user can switch templates without touching data.

## Available patterns

!`uv run ${CLAUDE_SKILL_DIR}/scripts/list_patterns.py`

## Workflow

Follow these steps automatically. Only ask the user when information is genuinely missing.

### Step 1 — Understand the input

Determine what the user gave you and where the CV project lives:

- **Markdown / plain text** → read directly.
- **Existing PDF CV** → extract text:
  ```bash
  uv run ${CLAUDE_SKILL_DIR}/scripts/ingest_pdf.py <path-to.pdf>
  ```
- **Pasted text in the conversation** → use as-is.
- **Photo**: only if the user mentions one or provided an image file in the working directory. Ask if the photo path is ambiguous.

Pick a **working directory** (the place the user wants `data.yaml` + PDF to live). Default: the current working directory. Do **not** write into the skill directory itself.

### Step 2 — Build or update `data.yaml`

The `data.yaml` file is the single source of truth. Schema: see [references/data-schema.md](references/data-schema.md).

- If `data.yaml` already exists in the working directory → read and update it rather than overwrite.
- Otherwise → create a new one from the raw input.
- Reference structure / full example: `${CLAUDE_SKILL_DIR}/examples/data.example.yaml`.

Required fields: `personal.name`. Everything else is optional but recommended.

**Ask the user** only if a field is genuinely missing AND the user's target template benefits from it. Typical missing items: target role / headline `title`, `available` (start date), photo path. Batch all questions into one turn.

### Step 3 — Pick a pattern

Default to `modern-sidebar` unless the user specifies another pattern or the argument `$1` is set. Check `meta.yaml.supports_photo` before keeping a photo in `data.yaml`.

### Step 4 — Render

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/build_cv.py \
  --data <working-dir>/data.yaml \
  --pattern <pattern-name> \
  --out <working-dir>/CV-<name>.pdf
```

The script:
- Embeds the photo as a base64 data URI (HTML is fully self-contained).
- Tries Edge → Chrome → Playwright (auto-installs chromium first time).
- Writes an HTML file next to the PDF for inspection.

### Step 5 — Report

Report to the user:
- Path to the generated PDF.
- Path to the rendered HTML (useful for fine-tuning).
- Path to `data.yaml` (so they know it's versionable).
- Any fields you inferred or skipped.

## Iteration patterns

**Fast preview** (no PDF, seconds not minutes):
```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/build_cv.py \
  --data data.yaml --pattern modern-sidebar \
  --no-pdf --html-out preview.html
```

**Switch template**: re-run with a different `--pattern`. Do not modify `data.yaml`.

**Add a new project / update a bullet**: edit `data.yaml`, re-run. Do not regenerate the whole file.

**Content overflows the page**: trim bullets in `data.yaml` first. Only edit the template as a last resort and only if the issue is general (not specific to this user's content).

## Arguments

`$1` — pattern name (optional). Example: `/cv-creator classic-single`.

If `$ARGUMENTS` looks like a file path (`.pdf`, `.md`, `.txt`, `.docx`), treat it as the raw input to ingest.

## Supporting files

- [references/data-schema.md](references/data-schema.md) — full data shape + all fields
- [references/pattern-authoring.md](references/pattern-authoring.md) — how to add a new template
- [references/pdf-troubleshooting.md](references/pdf-troubleshooting.md) — when rendering goes wrong
- `examples/data.example.yaml` — fully-filled example
- `schema/cv.schema.json` — authoritative JSON Schema

## Conventions

- **Language**: conversation in Chinese; all written CV content in English unless the user asks otherwise.
- **Scope**: one user per `data.yaml`. Multiple CV variants (e.g. "AI-focused" vs "backend-focused") live in separate working directories, each with their own `data.yaml`.
- **Never commit**: do not `git add`/`commit` the generated PDF or HTML without explicit user request.
- **Photo source**: only use a photo the user explicitly provides. Do not fabricate or download from the internet.
- **Data safety**: `data.yaml` may contain personal info (address, email). Keep it in the user's working directory, not in the skill dir.
