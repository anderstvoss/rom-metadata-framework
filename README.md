# ROM Metadata Framework

ROM Metadata Framework is a Linux-oriented Python framework for identifying ROM
and disc-image contents and resolving those identities into release metadata.

The project deliberately separates physical-file identity, container
representation, canonical content, canonical release identity, metadata
evidence, verification, and naming policy. This keeps platform-specific parsing
independent from provider lookup and prevents metadata enrichment from silently
changing identity or trust decisions.

## Status

The project is pre-1.0 and under active development.

The framework currently provides:

- physical CRC32, MD5, SHA1, and SHA256 identity;
- platform evidence and reconciliation;
- canonical-content normalization;
- physical-representation evidence;
- canonical release reconciliation;
- local structural metadata;
- independent provider metadata collection;
- metadata reconciliation without implicit provider precedence;
- verification policy;
- conservative naming plans;
- runtime capability reporting;
- an explicit consumer-facing Python API.

Platform and format support remains intentionally modular and incomplete.

## Current normalization support

The standard normalizer contains:

- NES normalization implemented directly by the framework;
- GameCube/Wii normalization backed by `dolphin-tool`;
- original-Xbox XDVDFS normalization backed by `xdvdfs`.

External backends are optional runtime dependencies. Missing backends are
reported explicitly and do not prevent an independent adapter from handling a
supported source.

See [Runtime Backends](docs/runtime-backends.md) for executable discovery,
capability reporting, probe semantics, temporary storage, and the command
contracts used by the framework.

## Development setup

The repository uses `uv` for the locked development environment.

```text
uv sync --frozen --extra dev
uv run --frozen pytest -q
uv run --frozen ruff check src tests
```

Before publishing changes, run:

```text
./scripts/pre-public-check
```

A distributable source archive and wheel can be built with:

```text
uv build
./scripts/check-package-artifacts
```

The artifact check validates package contents and installs the wheel into an
isolated environment before importing the public API.

## Python support

The package requires Python 3.11 or newer. Continuous integration exercises the
declared compatibility range across Python 3.11, 3.12, 3.13, and 3.14.

## Public API

The stable consumer-facing façade is exported from `rom_metadata_framework`.
Implementation adapters, backend wrappers, routing internals, and lower-level
provider machinery remain available from their defining modules but are not
part of the root stable API.

The primary root workflows are:

- `identify_file`
- `verify_identification`
- `collect_identification_metadata`
- `resolve_platform`
- `canonical_platform_name`

See the tests for the exact root export contract.

## Design goals

- Keep platform-specific identification behind modular adapters.
- Keep metadata providers independent from image parsing.
- Preserve physical representation separately from canonical content.
- Preserve local and provider metadata as independent evidence.
- Avoid implicit metadata precedence or first-provider-wins behavior.
- Support third-party-derived integrations only when licensing permits the
  intended use.
- Preserve explicit upstream attribution and provenance.
- Prefer external-tool boundaries when direct source reuse would create
  undesirable licensing coupling.
- Use synthetic or freely redistributable fixtures for public tests.
- Prevent ROM images, credentials, private infrastructure details, and local
  development data from entering public repository history.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Runtime Backends](docs/runtime-backends.md)
- [Metadata Selection Policy](docs/metadata-selection-policy.md)
- [Licensing Policy](docs/LICENSING.md)
- [Third-Party Provenance Policy](docs/THIRD_PARTY_PROVENANCE.md)
- [rcheevos Helper Contract](docs/RCHEEVOS_HELPER_CONTRACT.md)
- [Release Policy](docs/release-policy.md)

Repository contribution and security guidance is in
[CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

## Distribution boundary

The Python wheel contains the framework package plus applicable license/notice
material. External backend executables, helper binaries, commercial game
content, private validation corpora, and repository-only provenance/development
material are not bundled into the installed package.

The source distribution additionally contains public project documentation and
repository guidance needed to understand and build the released source.
