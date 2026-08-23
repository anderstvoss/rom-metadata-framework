# Contributing

ROM Metadata Framework is developed as a public, provenance-sensitive project.
Changes should preserve the separation between identification, normalization,
metadata, verification, and naming.

## Development environment

Use the locked `uv` environment:

```text
uv sync --frozen --extra dev
```

Run the baseline checks before opening a pull request:

```text
uv run --frozen ruff check src tests examples
uv run --frozen pytest -q
./scripts/pre-public-check
```

For packaging changes also run:

```text
uv build
./scripts/check-package-artifacts
```

## Change scope

Prefer focused branches and pull requests with one coherent architectural or
functional purpose. Avoid mixing platform additions, provider behavior,
packaging changes, and unrelated cleanup unless they are required by the same
contract.

Public API changes must update the explicit root-export tests.

## Test data

Do not commit commercial ROMs, disc images, extracted game executables, private
library content, credentials, tokens, or machine-specific validation paths.

Tests should use synthetic, original, or freely redistributable fixtures with
appropriate provenance.

## Third-party integrations

Before adding or materially changing an integration, review:

- `docs/LICENSING.md`
- `docs/THIRD_PARTY_PROVENANCE.md`

Material integrations must document the upstream project, license, integration
method, supported version or revision where practical, and redistribution
status.

Source-derived or redistributed integrations may require upstream license
copies and additional attribution.

## Architecture expectations

Keep these boundaries explicit:

- physical file identity is not canonical content identity;
- representation metadata is not release metadata;
- local metadata is not provider metadata;
- provider lookup is independent from local normalization evidence;
- metadata reconciliation is diagnostic, not selection;
- naming consumes canonical release identity and verification, not enrichment
  metadata;
- destructive file replacement must remain explicit rather than default.

## Pull requests

A pull request should state:

- what contract or behavior changed;
- why the change belongs at that layer;
- tests added or updated;
- external dependencies or provenance implications;
- public API impact;
- validation performed.
