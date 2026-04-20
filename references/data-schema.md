# CV data schema

The `data.yaml` file drives every pattern. Content (here) is separated from presentation (patterns). Switching templates only changes the `--pattern` flag.

Authoritative JSON Schema: `schema/cv.schema.json`. This doc is a human-readable guide.

## Contents

- Top-level fields
- `personal` (required)
- `summary`
- `work` and `projects`
- `education`
- `skills`
- `languages`
- `extras`
- Minimal and full examples

## Top-level fields

| Field        | Required | Type           | Purpose                                           |
|--------------|----------|----------------|---------------------------------------------------|
| `personal`   | **yes**  | mapping        | Identity, contact, photo                          |
| `summary`    | no       | string         | Short professional summary paragraph              |
| `work`       | no       | list           | Work experience entries                           |
| `projects`   | no       | list           | Project entries (same shape as work, `role` opt.) |
| `education`  | no       | list           | Degrees, language schools                         |
| `skills`     | no       | list of groups | Rendered as tag clouds by category                |
| `languages`  | no       | list           | Spoken languages + level                          |
| `extras`     | no       | list           | Scholarships, awards, certifications              |

## `personal` (required)

```yaml
personal:
  name: Alex Müller                # required
  title: Software Engineer         # headline role shown under the name
  photo: ./photo.png               # optional; relative to data.yaml
  birth: Berlin, Germany
  nationality: German
  address: Munich, Germany
  available: Immediately
  email: alex.mueller@example.com
  phone: "+49 123 456789"
  linkedin: linkedin.com/in/...
  github: github.com/...
  website: example.com
```

Only `name` is mandatory. Omit any field you don't want rendered.

**Photo**: path is resolved relative to the `data.yaml` file. At render time `build_cv.py` embeds it as a base64 data URI, so the generated HTML is fully self-contained.

## `summary`

```yaml
summary: >
  Software engineer with 6+ years of full-stack experience. Strong in
  backend systems, distributed architectures, and cloud infrastructure.
```

Use YAML `>` folded scalar for multi-line text that should render as one paragraph.

## `work` and `projects`

Same shape. `role` typically set for work, omitted for projects.

```yaml
work:
  - title: Acme GmbH              # required — company/project name
    role: Senior Software Engineer # optional — job title
    location: Munich, Germany      # optional
    date: 05/2023 – Present        # required — human-readable date range
    bullets:
      - Led migration of the billing platform to microservices ...
      - Designed an internal feature-flag service ...

projects:
  - title: Observability Sidecar
    date: 01/2024 – Present
    bullets:
      - Designed an open-source metrics/logs sidecar ...
```

Bullets are plain strings. Keep them impact-first and start with a verb in past tense (or present for current work).

## `education`

```yaml
education:
  - title: Example University of Technology   # required — institution
    date: 10/2017 – 04/2020                   # required
    location: Munich, Germany                 # optional
    degree: M.Sc. Computer Science (1.5)      # optional — bolded in output
    details: |                                # optional — free-form, multi-line
      Thesis: Deterministic scheduling for distributed workloads (1.3)
      Focus: Distributed Systems, Compilers, Formal Methods
```

## `skills`

Grouped into categories, each with a list of tag strings. Keep tag names short (single words or 2-word combos) so they fit the sidebar.

```yaml
skills:
  - category: Backend
    tags: [Go, Python, gRPC, PostgreSQL, Redis]
  - category: Cloud & DevOps
    tags: [AWS, Kubernetes, Terraform, Docker]
```

## `languages`

```yaml
languages:
  - { name: German,  level: Native }
  - { name: English, level: Fluent (C1) }
  - { name: French,  level: Basic (A2) }
```

## `extras`

Scholarships, awards, certifications. Each entry has `title`, optional `subtitle`, and optional `meta` (typically date + institution).

```yaml
extras:
  - title: Open Source Contributor Award
    subtitle: for sustained contributions to the observability ecosystem
    meta: CNCF, 2024
```

## Minimal example

```yaml
personal:
  name: Jane Doe
summary: Software engineer with 5 years of backend experience.
work:
  - title: Acme Corp
    role: Senior Engineer
    date: 2022 – Present
    bullets: [Built foo, Shipped bar]
```

## Full example

See `examples/data.example.yaml`.

## Validation

The build script parses YAML strictly. Missing required fields (`personal.name`, entry `title`/`date`) will raise an error with the field path. Unexpected keys outside this schema are silently passed through to the template context but are typically ignored by templates.

## YAML gotcha: colons in bullets

A bullet that contains `: ` (colon + space) is parsed by YAML as a mapping, not a string:

```yaml
# WRONG — parses as {'Owned CI/CD': 'GitHub Actions, Terraform'}
- Owned CI/CD: GitHub Actions, Terraform

# Correct — quote the whole bullet
- "Owned CI/CD: GitHub Actions, Terraform"

# Or rephrase without a colon
- Owned CI/CD using GitHub Actions and Terraform

# Or use an em dash
- Owned CI/CD — GitHub Actions, Terraform
```

The template has a `|flat` defensive filter that will still render such mistakes as `key: value`, but cleaner data is better. The same rule applies to `summary`, `bullets`, and `education[].details`.

