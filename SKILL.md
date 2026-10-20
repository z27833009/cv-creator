---
name: "cv-creator"
description: "Generates a printable, ATS-safe PDF CV from raw material (markdown, PDF, plain text, optional photo) using a chosen HTML/CSS template, can maintain multiple career-direction (\"angle\") variants of the same underlying experience, and can tailor any of them to a specific job posting. Use when the user wants to create, update, regenerate, restyle, or tailor their CV/resume for a job application or career direction, switch CV templates, or export a CV to PDF."
---


# CV Creator

Build a structured CV from raw input, render it through an HTML/CSS **pattern**, and produce a self-contained,
ATS-safe PDF. Content (`data.yaml`) is separated from presentation (patterns) so the user can switch templates
without touching data, and so the same underlying experience can be re-angled toward different career
directions and re-tailored per job application.

> Script paths below are relative to this skill's directory (the "Base directory for this skill" shown when this
> skill loads).

## Available patterns

List `patterns/` in this skill's directory. Each pattern has a `meta.yaml` (declares `supports_photo` and any
content limits — see "Known pattern limitations" below) and a `template.html.j2`.

## Workflow

Follow these steps automatically. Only ask the user when information is genuinely missing.

### Step 1 — Understand the input

Determine what the user gave you and where the CV project lives:

- **Markdown / plain text** → read directly.
- **Existing PDF CV** → extract text: `uv run scripts/ingest_pdf.py <path-to.pdf>`
- **Pasted text in the conversation** → use as-is.
- **Photo**: only if the user mentions one or provided an image file in the working directory. Ask if the photo
  path is ambiguous.

Pick a **working directory** (where `data.yaml` + PDF should live) — default to the user's existing CV folder if
one exists, otherwise the current working directory. Do **not** write into the skill directory itself.

### Step 2 — Build or update the master `data.yaml`

The master `data.yaml` file (or `data-<LANG>.yaml` per language, see Conventions) is the single source of truth
for the user's real, complete experience. Schema: see `references/data-schema.md`.

- If a master file already exists in the working directory → read and update it rather than overwrite.
- Otherwise → create a new one from the raw input.
- Reference structure / full example: `examples/data.example.yaml`.

Required fields: `personal.name`. Everything else is optional but recommended.

**Ask the user** only if a field is genuinely missing AND the target template benefits from it. Batch all
questions into one turn.

**Work vs. Projects overlap check**: before finalizing `work` and `projects`, check whether any `projects` entry
actually describes the same real-world work as a `work` entry — same employer's time period, same or heavily
overlapping technology/deliverables, just described from a different angle. This happens easily when someone
writes up their day job in more depth as a separate "project." If you find this, ask the user directly whether
the project entry is genuinely separate (done outside work hours, unrelated to the employer) or is the same job
described twice. If it's the same job, merge it into the `work` entry's bullets and remove the separate
`projects` entry — don't just leave both. Two sections independently describing the same RAG pipeline or the
same job's tech stack, with overlapping dates, reads as padding to a human reviewer even when every individual
claim is true. Reserve `projects` for genuinely distinct work: academic/thesis work, freelance/personal projects
done outside employment, coursework, open-source contributions.

### Step 3 — Pick a pattern

Default to `modern-sidebar` unless the user specifies another pattern. Check `meta.yaml.supports_photo` before
keeping a photo in `data.yaml`. See "Choosing a pattern for ATS-sensitive submissions" below before picking a
sidebar/photo pattern for a real job application.

### Step 4 — Render

```bash
uv run scripts/build_cv.py \
  --data <working-dir>/data.yaml \
  --pattern <pattern-name> \
  --out <working-dir>/CV-<name>.pdf
```

The script embeds the photo as a base64 data URI (HTML is self-contained), and tries Edge → Chrome → Playwright,
in that order, to produce the PDF.

**If Edge/Chrome/Playwright are all unavailable** (common in sandboxed/offline environments — Playwright's
browser download will fail with a network-allowlist error and there's no system Chrome): the script has no
built-in fallback. Do this instead:

1. Run the build with `--no-pdf --html-out <working-dir>/CV.html` to get the rendered HTML only.
2. `pip install weasyprint --break-system-packages` (pulls from PyPI, which is reachable even when browser CDNs
   are not).
3. Before converting, patch the generated HTML (not the pattern source — just this one output file) for two known
   WeasyPrint incompatibilities:
   - Any CSS rule with `font-variant: small-caps` on a header/label — WeasyPrint does not reliably synthesize
     small-caps glyphs, and some PDF text-extractors (e.g. `pypdf`) will read the result back as spaced-out
     letters ("S U M M A R Y"). Replace with `text-transform: uppercase;` plus an explicit smaller `font-size`.
   - Any `.tag`/`.pill`-style `<span>` with `border-radius` + a `background` (especially `rgba(...)`) inside a
     `display:flex; flex-wrap:wrap` container — WeasyPrint renders a visible double-edge/ghost-border artifact
     around each pill. This is a WeasyPrint fragmentation bug, not a CSS mistake (the same HTML renders correctly
     in real Chrome/Edge). The reliable fix (confirmed working, not just a workaround): drop `display:flex` +
     `gap` on the tag container entirely — use a plain block container with `display:inline-block` on each tag
     plus explicit `margin` (not `gap`) for spacing, and a **solid** background color (not `rgba(...)`). This
     fully eliminates the artifact. Only fall back to a non-pill pattern (e.g. `classic-single`'s comma-separated
     skills line) or a real-browser Print → Save as PDF if the tag styling must stay flex-based for some other
     reason.
   - CSS Grid combined with nested `display:flex; flex-direction:column` (common in sidebar patterns) can cause
     WeasyPrint to mis-paginate and emit extra blank trailing pages even when all content fits on one page. If
     this happens, verify the actual page count is a WeasyPrint artifact by checking that no content is missing
     (`pdftotext -layout` the file and confirm every section appears) before concluding the CV itself doesn't fit.
   - For a sidebar layout's left column to visually stretch to match a taller right column under WeasyPrint:
     CSS Grid `align-items: stretch` is unreliable, and `display:table`/`table-cell` causes min-height
     propagation issues. The pattern that reliably works: `display: flex; align-items: stretch` on the outer
     page container, with the sidebar column at a fixed `width` + `flex-shrink: 0` and the main column at
     `flex: 1`.
   - **Critical pagination trap**: setting a *fixed* `height` (e.g. `height: 297mm`) on `html, body` in a sidebar
     template causes WeasyPrint to silently **clip overflowing content** instead of creating a second page — the
     page-count self-check will report "1 page" even though real content (e.g. an entire education entry) is
     missing from the output, with no error or warning. Always use `min-height: 297mm`, never a fixed `height`,
     on `html`/`body`/the page container. After any render, cross-check rendered text against the source
     `data.yaml` (see Step 5) specifically for this failure mode — it is silent and page-count alone will not
     catch it.
   - Once patched: `weasyprint <working-dir>/CV.html <working-dir>/CV.pdf`.
4. Always tell the user explicitly when a WeasyPrint fallback was used and that a browser-rendered version (via
   `build_cv.py` on a machine with Chrome/Edge, or by opening the HTML and printing to PDF) is the higher-fidelity
   source of truth — especially for any pattern with photo/sidebar/tag-pill styling.

### Step 5 — Verify (do this every time, not just when something looks wrong)

- **Text layer**: every render prints a self-check (`text-layer: OK | FAILED`). Add `--strict` to fail the build
  on FAILED. A FAILED/non-selectable PDF will not parse in any ATS — treat this as a hard blocker, not a
  cosmetic issue.
- **Page count**: compare against the pattern's intended `max_pages` (see each target's config or the pattern's
  design intent). If it overflows by only a little, trim bullet wording before touching the template.
- **Cross-check with a second extractor** when in doubt: `pdftotext -layout file.pdf -` in addition to whatever
  the build script's self-check used. Different PDF text extractors handle letter-spacing/small-caps differently;
  agreement across two engines is a much stronger ATS-safety signal than either alone.
- **Content completeness**: diff the rendered text against `data.yaml` for anything that quietly didn't render —
  see "Known pattern limitations" below for the specific case this has caught before, and the fixed-`height`
  pagination trap in Step 4 above (the single most damaging failure mode found so far, because it drops entire
  sections with zero error signal).
- **Flow-mapping YAML with commas**: if a value written in `{ key: value, key: value }` flow-mapping shorthand
  contains its own comma (e.g. a language level like `Good (B2, DSH-2)`), YAML parses that comma as a new key
  separator and silently truncates the value. Quote any flow-mapping value that contains a comma:
  `{ name: German, level: "Good (B2, DSH-2)" }`. Spot-check the rendered Languages/Extras lines against the
  source YAML — a truncated value (missing closing parenthesis, cut-off text) is the tell.
- **Hyphenated word split across a YAML folded-scalar (`>`) line break**: if a hyphenated compound word (e.g.
  "cross-functional") happens to span a line break inside a `>` block scalar, YAML's folding rule inserts a
  space at the fold point, producing "cross- functional" (extra space) in the rendered output. Keep hyphenated
  compound words on a single source line inside folded scalars.

### Step 6 — Maintain multiple career-direction ("angle") variants

A person's real experience often genuinely supports more than one career direction (e.g. an AI engineer whose
work also includes solid data-engineering and full-stack-software evidence). When the user wants to target more
than one direction, don't just keep re-tailoring one narrative — maintain **separate angle-level master files**:

1. Naming: `data-<LANG>-<Angle>.yaml`, e.g. `data-EN-DataScience.yaml`, `data-EN-FullStack.yaml`,
   `data-EN-CloudDevOps.yaml`, alongside the default/primary `data-<LANG>.yaml`.
2. Each angle file draws from the **same real work history** — same employers, same dates, same projects — but
   reorders, reweights, and rewords the summary/bullets/skills to lead with the angle's terminology, and
   reorders skill categories so the angle's core stack comes first. Do not invent new employers, projects, tools,
   or responsibilities for an angle; only emphasis and framing change.
3. Before building a new angle, honestly assess whether the real experience supports it: does the work history
   contain genuine, substantive evidence for that direction, or would the angle file be mostly relabeling the
   same AI/LLM bullets with different buzzwords? If the evidence is thin (e.g. the user has only ever used a
   cloud platform to deploy their own applications, not run production infrastructure), say so plainly and
   recommend against building that angle as a standalone master file — offer to fold it into a closer-fitting
   angle instead when a specific posting needs it. A resume can reweight true experience; it cannot manufacture
   depth that isn't there, and a reviewer in that specialty will notice at the first technical question.
4. Render and verify each angle file per Steps 4–5, same as any other `data.yaml`.
5. Job-specific tailoring (Step 7) then starts from whichever angle file is the closest match to a given posting,
   not always from the default/primary one.

### Step 7 — Tailor for a specific job posting (when the user gives you a JD)

Do this as a distinct pass, after the base (or angle) CV is solid:

1. Fetch/read the full job description. Extract the required and preferred hard-skill keywords, tools, and
   domain terms verbatim (e.g. specific frameworks, methodologies, system names).
2. Pick the closest-matching source file — the default `data-<LANG>.yaml` or, if one exists, the angle file
   whose framing already leans toward this posting (Step 6). Copy it to a job-specific file — naming convention:
   `data-<LANG>-<Company>.yaml` (e.g. `data-EN-BASF.yaml`). Never overwrite the master/angle file it came from.
3. Edit only wording, ordering, and emphasis — rewrite the summary and reorder/reword bullets and skill tags to
   surface the JD's exact terminology wherever it is truthfully supported by the user's real experience. Do not
   invent tools, systems, or experience the user hasn't actually had, even if the JD asks for them — leaving a
   genuine gap unaddressed is always preferable to fabricating a match. If a JD leans heavily on requirements
   with no genuine backing anywhere in the master/angle data (e.g. a mandatory language level the user doesn't
   actually have, or a core responsibility with zero real supporting evidence), say so directly and ask whether
   the user still wants to proceed before spending effort tailoring — don't silently produce a stretched CV for
   a JD that's a poor match.
4. Re-render following Steps 4–5, output as `CV-<Name>-<LANG>-<Company>.pdf` next to the job-specific data file.
5. Report which JD keywords are now covered and which genuine gaps remain, so the user knows what a human
   reviewer might still flag.
6. Before finalizing, run every job-specific file through the "Content-balance checklist" below — this has been
   the single biggest source of user dissatisfaction with tailored variants, more than wording choices.

## Content-balance checklist (apply to every job-specific tailored CV, not just the master)

When tailoring toward a specific posting, it's easy to over-trim in the name of relevance and end up with a CV
that reads as thin or lopsided even though every individual line is accurate. Check all of the following before
calling a tailored CV done:

- **Don't shrink the skills section down to only the JD's exact keywords.** A tailored CV should *reorder* skill
  categories so the JD's core stack leads, and may trim categories that are genuinely irrelevant to the role
  family (e.g. dropping a "Data Visualization" category for a pure backend-infra role), but should still show
  the person's real breadth — aim for the same number of categories and roughly the same tag density as the
  master/angle file it was copied from, not a bare 3–4 categories with 4–5 tags total. A skills section that
  shrinks every time makes someone look less capable with every new tailored version, which is the opposite of
  the goal.
- **Keep work-experience bullet counts roughly balanced across employers.** The most recent/most relevant job
  (e.g. the current AI Engineer role) will naturally get somewhat more space than older or less relevant roles,
  but the ratio should stay reasonable — roughly 3–4 bullets for the lead role against 2–3 for the next one and
  2 for the oldest, not 4 vs. 1 vs. 1. A tailored CV that hollows out every job except the most recent one to
  a single bullet reads as padding on the top role rather than a genuine full career picture, and looks
  noticeably worse than the master CV it was derived from.
- **Keep education entries similarly balanced.** If the most recent/advanced degree gets 2–3 bullets (thesis,
  seminar projects, scholarship, etc.), don't reduce an earlier degree (e.g. the Bachelor's) down to a single
  "Focus: ..." line when the master file has a fuller treatment (e.g. a Bachelor's-thesis line) available —
  carry that fuller version through into tailored variants unless space genuinely doesn't allow it.
- **Never mention gRPC in Jiajun Zhou's CV, in any variant, for any job.** This was implemented with heavy AI
  assistance, he is not comfortable defending it in a technical interview, and he has said explicitly and
  repeatedly not to include it. If a Go↔Python service bridge needs to be described, describe it by outcome
  (e.g. "connecting a Go gateway to Python agent services so tool governance is implemented once and reused")
  without naming the specific RPC protocol used underneath.
- **Represent his Terraform/Azure/CI-CD infrastructure work with real depth, not a generic one-liner.** The
  strongest, most verified version of this experience is the infrastructure-provisioning-engine work at SIMO
  GmbH: a Go-based orchestration engine across roughly 8 Terraform modules (network, compute, Key Vault,
  container registry, backup), with a versioned Terraform state-snapshot system that makes upgrades safe and
  incremental instead of full rebuilds, secured via Managed Identity/RBAC and Key Vault (no shared credentials),
  deployed via GitHub Actions CI/CD. Do not name the internal product ("Bootstrap") if the user hasn't asked for
  it named, but do carry the substance (module count, versioned-state mechanism, security model) into any bullet
  describing his cloud/IaC experience — a generic "deployed on Azure with CI/CD pipelines" line understates
  real, verifiable depth he actually has and has been flagged as a regression when it replaces the fuller
  version.

## Choosing a pattern for ATS-sensitive submissions

For a real job application (as opposed to a portfolio piece), prefer single-column, plain-text-section patterns
(`classic-single`, `timeline`) over sidebar/photo patterns (`modern-sidebar`, `en-sidebar`, `de-sidebar`,
`zh-sidebar`) when the user's priority is passing automated screening reliably:

- Single column avoids any risk of an ATS reading across two columns and interleaving text incorrectly.
- No photo avoids inconsistent handling by different ATS/OCR pipelines (and photos carry no ATS benefit — they're
  simply skipped by any text-based parser).
- These patterns also render correctly under the WeasyPrint fallback above, with no known artifacts.

Sidebar/photo patterns are a reasonable choice when human visual impression matters more than parsing risk (e.g.
markets/roles where a photo is customary and the application isn't a pure keyword-matched ATS funnel), or once
verified via a real browser render. When unsure, offer the ATS-safe pattern as the default and the sidebar
pattern as an optional visual alternative to compare, not the default deliverable.

## Known pattern limitations

- `en-sidebar` and `de-sidebar` show at most **2 project entries** regardless of how many are in `data.yaml`
  (`{% for p in projects[:2] %}` in the template) — this is a deliberate one-page space constraint, but it fails
  silently. If the user's `projects` list has 3+ entries, tell them explicitly which ones will be dropped, or
  suggest trimming `projects` in the job-specific data file to the 2 most relevant before rendering.
- `en-sidebar`/`de-sidebar`/`zh-sidebar` filter out education entries whose title contains "Language" /
  "Sprachschule" / "语言" (language-school entries are hidden by design, to save space) — this is intentional,
  not a bug, but worth knowing before wondering where an entry went.
- `classic-single`'s skills-line labels use `font-variant: small-caps` in the shipped template — safe under real
  Chrome/Edge rendering, but apply the Step 4 WeasyPrint patch if falling back to WeasyPrint.
- A `zh-sidebar` (or any CJK-language) variant needs an explicit CJK-capable font in the `font-family` stack
  (e.g. `'Noto Sans CJK SC', 'Noto Sans SC'`) ahead of the Latin fallback fonts — the default Latin-only stack
  used by the English/German patterns renders Chinese/Japanese/Korean text as empty boxes or nothing under
  WeasyPrint. Section headers/labels inside the template are hardcoded per language file, so a CJK variant needs
  its own copy of the template with translated labels, not just a data-file swap.

## Iteration patterns

**Fast preview** (no PDF, seconds not minutes):
```bash
uv run scripts/build_cv.py --data data.yaml --pattern modern-sidebar --no-pdf --html-out preview.html
```

**Switch template**: re-run with a different `--pattern`. Do not modify `data.yaml`.

**Add a new project / update a bullet**: edit `data.yaml`, re-run. Do not regenerate the whole file. If the
change reflects new real-world experience (not just rewording), propagate it to the master file and to every
angle file that draws from it, not just the one you happened to be editing.

**Render an existing HTML file directly** (skip templating):
```bash
uv run scripts/build_cv.py --from-html path/to/cv.html --out path/to/cv.pdf
```

**Content overflows the page**: trim bullets in `data.yaml` first. Only edit the template as a last resort and
only if the issue is general (not specific to this user's content).

**PDF text not selectable**: see `references/pdf-troubleshooting.md`. Add `--strict` to fail the build when the
check fails.

## Arguments

`$1` — pattern name (optional). Example: `/cv-creator classic-single`. If it looks like a file path (`.pdf`,
`.md`, `.txt`, `.docx`), treat it as the raw input to ingest.

## Supporting files

- `references/data-schema.md` — full data shape + all fields
- `references/pattern-authoring.md` — how to add a new template
- `references/pdf-troubleshooting.md` — when rendering goes wrong
- `examples/data.example.yaml` — fully-filled example
- `schema/cv.schema.json` — authoritative JSON Schema

## Conventions

- **Language**: conversation in Chinese; all written CV content in English unless the user asks otherwise.
- **File hierarchy**: one master `data-<LANG>.yaml` per language, holding the complete, real work history.
  Career-direction variants are `data-<LANG>-<Angle>.yaml` (Step 6). Job-specific tailored variants are
  `data-<LANG>-<Company>.yaml` (Step 7), each derived from the master or the closest-matching angle file. All
  three tiers live together in the same working directory (not separate subfolders), matched by their
  `CV-<Name>-<LANG>-[<Angle>|<Company>].pdf` output, so the whole family stays easy to find and diff.
- **Never commit**: do not `git add`/`commit` generated PDFs or HTML without explicit user request.
- **Photo source**: only use a photo the user explicitly provides. Do not fabricate or download from the internet.
- **Data safety**: `data.yaml` may contain personal info (address, email). Keep it in the user's working
  directory, not in the skill dir.

