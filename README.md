# ROM Metadata Framework

ROM Metadata Framework is a Linux-oriented Python framework and command-line
tool for identifying ROM, package, and disc-image contents and resolving those
identities into release metadata.

The project deliberately separates:

- physical-file identity;
- platform detection;
- physical/container representation;
- canonical or normalized content;
- artifact-local structural metadata;
- provider/catalogue release identity;
- metadata enrichment;
- verification;
- naming and file-operation policy.

This prevents container details, provider ordering, or descriptive metadata
from silently changing identity or trust decisions.

## Status

ROM Metadata Framework is pre-1.0 and under active development.

Platform coverage is intentionally incremental. A platform being registered in
the canonical registry or having a provider mapping does not necessarily mean
the standard runtime currently implements detection or parsing for that
platform.

Canonical platform identifiers use concise community ROM/emulation slugs such
as `nes`, `snes`, `gc`, `ps2`, `ps3`, `xbox360`, and `switch`. Human-readable
platform names and manufacturers are maintained separately, while older
long-form framework identifiers remain accepted as aliases.

## Installation

The package requires Python 3.11 or newer.

To install a locally built wheel:

~~~text
python -m pip install dist/rom_metadata_framework-*.whl
~~~

Package-index publication is not currently part of the project's release
workflow.

For repository development:

~~~text
uv sync --frozen --extra dev
~~~

The Python package has no mandatory third-party Python runtime dependencies.
Some normalization paths use optional external executables.

See [Runtime Backends](docs/runtime-backends.md).

## Command-line interface

Installation provides:

~~~text
rom-metadata
~~~

The command set is:

~~~text
rom-metadata platforms
rom-metadata capabilities
rom-metadata inspect PATH
rom-metadata identify PATH
rom-metadata plan-rename PATH
rom-metadata rename PATH
rom-metadata verify PATH
~~~

Examples:

~~~text
# Show implementation coverage.
rom-metadata platforms

# Show optional backend readiness.
rom-metadata capabilities

# Bounded local detection/inspection; no whole-file hashing or provider lookup.
rom-metadata inspect game.iso

# Whole-file hashing plus standard release identification.
rom-metadata identify game.iso

# Show available physical-file and represented-content hashes.
rom-metadata identify game.iso --hashes

# Concise machine-readable identification.
rom-metadata identify game.iso --json

# Full diagnostic identification evidence.
rom-metadata identify game.iso --json --complete

# Preview a verified canonical filename without changing the file.
rom-metadata plan-rename game.iso

# Rename to a verified canonical filename after interactive confirmation.
rom-metadata rename game.iso

# Skip only the confirmation prompt; safety and collision checks remain active.
rom-metadata rename game.iso --yes

# Prefer or restrict platform/native-identity handling.
rom-metadata identify game.iso --platform wii
rom-metadata identify game.iso --identity wii:ABCD01
rom-metadata identify game.iso --identity wii:ABCD01 --restrict

# Identification plus catalogue-backed verification policy.
rom-metadata verify game.iso
~~~

All commands support `--help`. Structured commands support `--json`.

The normal `identify` output is concise and favors useful release information
such as title, platform, region, platform-native identifier, revision, disc
position, and physical source format when available. Strong local structural
identification can remain useful when the catalogue provider has no match or is
temporarily unavailable.

`identify`, `plan-rename`, `rename`, and `verify` may perform network requests
through Playmatch and may invoke optional normalization backends. `inspect`
remains bounded and local.

Path-oriented commands support directed platform/identity selection.
`--platform` and `--identity PLATFORM:ID` are soft preferences by default:
the requested handling is tried first, but ordinary discovery may still fall
back when it does not match. Adding `--restrict` makes the selection a hard,
compute-saving restriction and prevents unrelated platform work.

`--identity` is a hypothesis about platform-native identity, not an instruction
to force metadata onto a mismatched file.

See the full [CLI Reference](docs/cli.md) for command semantics, exit codes,
network behavior, and the pre-1.0 JSON compatibility policy.

## Supported platforms

The table below describes the **standard runtime**, not merely registry or
provider-mapping presence.

| Platform | Detection | Structural inspection | Normalization | Integrity | Current handling |
| --- | --- | --- | --- | --- | --- |
| NES | Built in | — | Built in | — | iNES/NES content support; headerless normalization is explicit opt-in |
| GameCube | External | — | External | — | Detection and canonical reconstruction through `dolphin-tool` |
| Wii | External | — | External | — | Detection and canonical reconstruction through `dolphin-tool` |
| PlayStation 2 | Built in | Built in | — | — | Bounded ISO9660 `SYSTEM.CNF` / `BOOT2` detection and local metadata |
| PlayStation 3 | Built in | Built in | — | — | Directly readable ISO9660 disc images; encrypted/raw representations are not decoded |
| Xbox | External | — | External | — | Original-Xbox XDVDFS handling through the `xdvdfs` backend |
| Xbox 360 | Built in | Built in | — | — | Bounded XDVDFS/XEX2 detection and structural metadata |
| Nintendo Switch | Built in | Built in | — | — | Bounded NSP/PFS0 and XCI/HFS0 structural handling; no NCA decryption |

`rom-metadata platforms` is the machine-readable/runtime-facing source for the
current support inventory.

### Detection, inspection, normalization, and integrity are different

A platform does not need every capability.

**Detection** determines which platform an artifact appears to belong to.

**Structural inspection** extracts representation and artifact-local facts
without creating canonical content.

**Normalization** is used only where the framework has a defensible transform
to a canonical content identity.

**Integrity verification** is platform-specific validation of the physical
artifact or media and remains distinct from catalogue-backed release
verification.

For that reason, PlayStation 2, PlayStation 3, Xbox 360, and Nintendo Switch
currently have useful detection/inspection support without a normalizer.

## Registered and planned platforms

The canonical registry also currently contains these platforms without
standard-runtime detector/inspection/normalization support:

- SNES;
- Sega Genesis / Mega Drive;
- Nintendo 64;
- Game Boy;
- Game Boy Color;
- Game Boy Advance;
- PlayStation;
- Nintendo DS;
- PSP.

These entries represent registry/provider groundwork and likely future
expansion areas. They are **not implementation commitments, release dates, or
claims of current ROM-format support**.

Future platform work is expected to continue incrementally, with detection,
structural parsing, normalization, and provider integration evaluated
independently for each platform.

See [Adding a Platform](docs/adding-a-platform.md) for the contribution model.

## Identification pipeline

At a high level:

~~~text
physical file
   |
   +--> whole-file identity/hashes ----------> physical provider lookup
   |
   +--> platform detection
   |
   +--> bounded structural inspection
   |       +--> representation
   |       +--> local metadata
   |
   +--> optional canonical normalization
           +--> normalized content identity
           +--> normalized provider lookup
                         |
                         v
                release reconciliation
                         |
                         v
                canonical release identity
~~~

Physical provider lookup occurs before optional structural inspection and
normalization.

Structural inspection alone never initiates normalized provider lookup.

See [Architecture](docs/ARCHITECTURE.md) for the complete model.

## Python API

The stable consumer-facing Python façade is exported from
`rom_metadata_framework`.

The primary root workflows include:

- `identify_file`;
- `verify_identification`;
- `collect_identification_metadata`;
- `resolve_platform`;
- `canonical_platform_name`.

Implementation adapters, backend wrappers, routing internals, and provider
machinery remain available from their defining modules but are not part of the
stable root façade.

Example:

~~~python
from pathlib import Path

from rom_metadata_framework import identify_file
from rom_metadata_framework.defaults import (
    DefaultRuntimeConfig,
    build_default_detector,
    build_default_inspector,
    build_default_normalizer,
)
from rom_metadata_framework.playmatch import PlaymatchResolver

config = DefaultRuntimeConfig()

result = identify_file(
    Path("game.rom"),
    detector=build_default_detector(config),
    resolver=PlaymatchResolver(),
    inspector=build_default_inspector(config),
    normalizer=build_default_normalizer(config),
)

if result.identified:
    print(result.canonical_match.release_name)

if result.has_local_metadata:
    print(result.local_metadata)
~~~

See [Getting Started](docs/getting-started.md) and the runnable programs in
[`examples/`](examples/).

## Verification

Verification is evidence based.

The current CLI `verify` command evaluates catalogue-backed release evidence.
It is deliberately distinct from future specialist integrity verification such
as optical-disc sector validation, IRD-based validation, or platform
cryptographic signature verification.

The Python API also preserves physical and normalized verification evidence
independently so that trust in normalized content does not automatically imply
that an arbitrary physical representation is known-good.

## Naming and file operations

Canonical naming consumes release identity and verification state, not
descriptive metadata enrichment.

The legacy naming path preserves provider canonical release names. A structured
identification-aware path can additionally use a clean canonical title plus
agreeing artifact-local evidence such as the primary platform identifier,
country/region, and non-default revision. It does not heuristically parse
provider release-name strings.

The naming APIs remain non-mutating by default and can produce a
copy/new-file plan without changing the source.

The CLI additionally provides an explicit `rename` operation. It performs the
same identification and verification checks, proposes the structured canonical
filename, and mutates only after confirmation (or `--yes`). `--yes` bypasses
only the prompt: it does not bypass identity conflicts, verification policy,
path safety, or destination-collision checks.

Executable rename remains within the source directory and never overwrites an
existing destination.

## Development

Run:

~~~text
uv run --frozen ruff check src tests examples
uv run --frozen pytest -q
./scripts/pre-public-check
~~~

For packaging changes:

~~~text
uv build
./scripts/check-package-artifacts
~~~

Public tests must not contain commercial ROM data, private validation-corpus
identifiers, credentials, or machine-specific private paths.

## Documentation

- [Getting Started](docs/getting-started.md)
- [CLI Reference](docs/cli.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Adding a Platform](docs/adding-a-platform.md)
- [Runtime Backends](docs/runtime-backends.md)
- [Provider and Platform Coverage](docs/provider-platform-coverage.md)
- [Metadata Selection Policy](docs/metadata-selection-policy.md)
- [Licensing Policy](docs/LICENSING.md)
- [Third-Party Provenance Policy](docs/THIRD_PARTY_PROVENANCE.md)
- [rcheevos Helper Contract](docs/RCHEEVOS_HELPER_CONTRACT.md)
- [Release Policy](docs/release-policy.md)

Contribution and security guidance is in [CONTRIBUTING.md](CONTRIBUTING.md) and
[SECURITY.md](SECURITY.md).

## Distribution boundary

The wheel contains the Python framework and applicable license/notice material.

External backend executables, helper binaries, commercial game content,
private validation corpora, local machine configuration, and credentials are
not bundled into the installed package.

The source distribution additionally contains public project documentation and
repository guidance needed to understand and build the released source.
