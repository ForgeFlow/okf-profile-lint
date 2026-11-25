# okf-profile-lint

Check [Open Knowledge Format](https://okf.md/) (OKF) bundles: conformance to
the spec, and the rules each bundle declares for itself.

OKF describes knowledge as a folder of Markdown files with a small YAML header,
one concept per file, so that people and AI agents can both read it. The spec
is deliberately tolerant: consumers must accept broken links, missing
descriptions and unknown types. A team that maintains a bundle usually wants
more than that. `okf-profile-lint` runs:

- **OKF 0.3 conformance**, with the
  [reference validator](https://github.com/open-knowledge-format/open-knowledge-format/tree/main/skills/okf-generate/scripts)
  of the OKF project;
- **the bundle's profile**: the rules it declares in an `okf-profile.yaml`,
  such as required fields, allowed values, a type per directory, no broken
  links, and every concept listed in its index. Every rule is off unless the
  profile turns it on, so the tool imposes no conventions of its own.

It does one thing: checking. Publishing a bundle as a website is left to the
bundle and its site generator.

Why a profile? OKF deliberately defines no taxonomy: which types exist, which
fields a concept needs, and where each type lives are decisions of the team
that maintains the bundle. A linter with a fixed rule set either imposes its
own house style or stays silent. `okf-profile-lint` checks the house style the
bundle itself declares, and conformance with the reference implementation of
the spec, so it does not lag behind new OKF versions.

## Install

```bash
pip install "okf-profile-lint @ git+https://github.com/ForgeFlow/okf-profile-lint@v0.1.0"
```

Python 3.10 or later.

## Linting a bundle

```bash
okf-profile-lint path/to/bundle   # exit 1 on errors
okf-profile-lint --strict         # also fail on warnings
okf-profile-lint --json           # machine-readable findings
```

Without an `okf-profile.yaml`, only OKF conformance is checked. With one, the
profile rules run as well. Every rule is off unless the profile turns it on:

```yaml
# okf-profile.yaml, at the bundle root
ignore: ["build/**"]                  # paths that are not part of the bundle
non_concepts: [README.md, STYLE.md]   # files without frontmatter on purpose
types:
  by_directory:                       # a directory name anywhere in the path
    references: Reference
    examples: Example
  default: Concept                    # every other concept
fields:
  required: [title, description, status]
  forbidden: [generated]
  values:
    status: [draft, stable, deprecated]
rules:
  ascii_only: true                    # no curly quotes, dashes or other non-ASCII
  title_heading: true                 # the first "# " heading equals the title
  listed_in_index: true               # every concept is listed in its index.md
  broken_links: true                  # links must resolve...
  planned_marker: "(planned)"         # ...unless an index lists the target as planned
```

| Code | Rule |
|---|---|
| `P001` | Non-ASCII character (`ascii_only`) |
| `P002` | A Markdown file without frontmatter that is not in `non_concepts` |
| `P003` | `type` differs from the one expected for the directory |
| `P004` | A required field is missing or empty |
| `P005` | A forbidden field is present |
| `P006` | A field value outside its allowed values |
| `P007` | The first level-1 heading differs from `title` (`title_heading`) |
| `P008` | Broken link not marked as planned (`broken_links`) |
| `P009`, `P010` | Concept directory without `index.md`, or concept not listed in it (`listed_in_index`) |

Codes starting with `E`, `W` and `I` come from the OKF reference validator.
When `broken_links` is on, its broken-link warning (`W115`) is replaced by
`P008`, which knows about planned entries.

### pre-commit

```yaml
repos:
  - repo: https://github.com/ForgeFlow/okf-profile-lint
    rev: v0.1.0
    hooks:
      - id: okf-profile-lint
```

## Development

```bash
python -m venv .venv
.venv/bin/pip install -e ".[test]"
.venv/bin/pytest
```

The OKF reference validator is vendored, unmodified, in
`src/okf_profile_lint/vendor/`; see the `README.md` there for its source commit and
how to update it.

## License

Apache License 2.0. See `LICENSE` and `NOTICE`.
