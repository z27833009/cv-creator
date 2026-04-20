# cv-creator

A [Claude Code](https://claude.com/code) skill that turns raw CV material (markdown, PDF, plain text, optional photo) into a polished, printable PDF using interchangeable HTML/CSS templates.

> **中文简介**：一个 Claude Code 的 skill，把原始简历素材（md / pdf / 文字 / 照片）通过可切换的 HTML/CSS 模板渲染成 PDF。数据和样式分离 —— 改模板不用重写内容。

---

## Why

Writing a CV is annoying. Every time you want to try a different style you end up rewriting the same content. This skill separates content from presentation:

- Your data lives in one `data.yaml` file — the single source of truth.
- Switching templates only changes a flag; no content edits needed.
- Claude Code drives the full loop: ingest old CVs, update fields, regenerate PDFs on demand.

---

## Features

- **3 built-in templates** — pick one or add your own:
  - `modern-sidebar` — dark navy two-column layout with teal accents and photo
  - `classic-single` — black-and-white, Georgia serif, formal and traditional (no photo)
  - `timeline` — vertical timeline with circular avatar, blue accents
- **Content / presentation separation** — one `data.yaml`, many templates
- **Self-contained PDFs** — photos are base64-embedded; no external dependencies in the generated HTML
- **Zero-install PDF rendering** — uses built-in Microsoft Edge or Google Chrome headless; auto-falls back to Playwright if neither is available
- **Progressive disclosure** — SKILL.md stays under the [official](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) 500-line limit; reference docs load only when needed
- **Defensive rendering** — gracefully handles common YAML mistakes (e.g. colons in bullets that accidentally create nested mappings)
- **Multi-page aware** — sidebar stripe repeats correctly across printed pages via `position: fixed`
- **Extensible** — adding a new pattern is one directory: copy, tweak CSS, done

---

## Templates at a glance

| Pattern | Photo | Pages | Accent | Use case |
|---------|-------|-------|--------|----------|
| **modern-sidebar** | yes | 1–2 | `#56c8c4` (teal) | Tech / AI roles, dense content |
| **classic-single** | no  | 1–3 | black | Finance, consulting, law, conservative industries |
| **timeline** | yes  | 1–2 | `#2563eb` (blue) | Product / software roles, visual storytelling |

Screenshots: _add your own renders here_

---

## Requirements

- [Claude Code](https://claude.com/code)
- [uv](https://docs.astral.sh/uv/) — handles Python dependencies via PEP 723 inline script metadata, so you don't need to manage a virtualenv
- One of the following for PDF output (auto-detected):
  - Microsoft Edge (built into Windows 11) — preferred
  - Google Chrome
  - [Playwright](https://playwright.dev/) (auto-installed on first run if no browser is found)

---

## Installation

Clone into your Claude Code personal skills directory:

```bash
# Linux / macOS
git clone https://github.com/<you>/cv-creator.git ~/.claude/skills/cv-creator

# Windows (Git Bash)
git clone https://github.com/<you>/cv-creator.git /c/Users/<you>/.claude/skills/cv-creator
```

Claude Code watches the skills directory and picks up the new skill within the current session — no restart needed.

Verify it's loaded:

```bash
# In Claude Code
/cv-creator
```

---

## Quick start

```bash
# 1. Create a working directory for your CV project
mkdir ~/Documents/my-cv && cd ~/Documents/my-cv

# 2. Put your raw material there (any combination):
#    - an old CV PDF
#    - a markdown file with your experience
#    - a plain text dump
#    - a passport-style photo

# 3. Start Claude Code
claude

# 4. Invoke the skill (examples):
#    /cv-creator
#    "Generate a CV from old-cv.pdf and photo.jpg"
#    "Add a new project X to my CV and re-render with the timeline template"
```

Claude will:

1. Read your raw material
2. Build or update `data.yaml` in the current directory
3. Ask only for fields that are genuinely missing (target role, start date, etc.)
4. Render HTML and PDF with the chosen pattern
5. Report the output paths

Output files land next to `data.yaml`:

```
my-cv/
├── data.yaml                  (single source of truth — reuse for every render)
├── CV-<name>.pdf              (generated)
├── CV-<name>.html             (generated, useful for inspection)
└── photo.jpg                  (optional)
```

---

## Direct script usage

You can also call the builder directly, bypassing Claude:

```bash
uv run ~/.claude/skills/cv-creator/scripts/build_cv.py \
  --data data.yaml \
  --pattern timeline \
  --out CV.pdf
```

Useful flags:

- `--pattern <name>` — pick a template from `patterns/`
- `--no-pdf --html-out preview.html` — fast HTML-only preview
- `--engine edge|chrome|playwright|auto` — force a specific PDF engine

Run `--help` for the full list.

---

## Data format

A minimal `data.yaml`:

```yaml
personal:
  name: Jane Doe
  title: Software Engineer
summary: Backend engineer with 5 years of experience.
work:
  - title: Acme Corp
    role: Senior Engineer
    date: 2022 – Present
    bullets:
      - Built the billing platform.
      - Shipped feature X.
```

Full schema + every supported field: [`references/data-schema.md`](references/data-schema.md).
JSON Schema for tooling: [`schema/cv.schema.json`](schema/cv.schema.json).
A fully-filled example to copy from: [`examples/data.example.yaml`](examples/data.example.yaml).

---

## Project layout

```
cv-creator/
├── SKILL.md                   Skill entry: frontmatter + workflow + links
├── schema/cv.schema.json      Authoritative data contract
├── examples/data.example.yaml Fully-filled reference CV
├── patterns/                  HTML/CSS templates (swap at render time)
│   ├── modern-sidebar/
│   │   ├── template.html.j2
│   │   └── meta.yaml
│   ├── classic-single/
│   └── timeline/
├── scripts/
│   ├── build_cv.py            Main renderer (data + pattern → HTML → PDF)
│   ├── ingest_pdf.py          Extract text from an existing PDF CV
│   └── list_patterns.py       Enumerate available patterns (dynamic in SKILL.md)
└── references/                Long-form docs, loaded on demand by Claude
    ├── data-schema.md
    ├── pattern-authoring.md
    └── pdf-troubleshooting.md
```

Following the [Agent Skills](https://agentskills.io/) open standard, with Claude Code extensions where helpful.

---

## Adding your own pattern

```bash
cd ~/.claude/skills/cv-creator
cp -r patterns/modern-sidebar patterns/my-pattern
# Edit patterns/my-pattern/template.html.j2 and meta.yaml
```

Then:

```bash
uv run scripts/build_cv.py --data data.yaml --pattern my-pattern --out CV.pdf
```

Full authoring guide (context variables, print CSS tips, common pitfalls): [`references/pattern-authoring.md`](references/pattern-authoring.md).

---

## Troubleshooting

When PDF rendering misbehaves (background missing, photo blank, fonts wrong), work through [`references/pdf-troubleshooting.md`](references/pdf-troubleshooting.md). The guide covers engine selection, `print-color-adjust` gotchas, CJK fallback, and the fast HTML-only iteration loop.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Credits

Built with [Claude Code](https://claude.com/code). Follows the [Agent Skills open standard](https://agentskills.io/). PDF rendering powered by [Playwright](https://playwright.dev/) / Chromium headless.
