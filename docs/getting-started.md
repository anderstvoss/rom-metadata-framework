# Getting Started

## Install the development environment

The repository uses `uv`.

~~~text
uv sync --frozen --extra dev
~~~

The Python package itself has no mandatory Python dependencies beyond the
standard library.

Some platform normalization features use optional external executables. See
[Runtime Backends](runtime-backends.md).

## Check runtime capabilities

Run:

~~~text
uv run --frozen python examples/runtime_capabilities.py
~~~


The standard detector composition includes NES, PlayStation 2,
PlayStation 3, GameCube/Wii, and original Xbox detection. Structural
inspection is enabled for PlayStation 2 and directly readable
PlayStation 3 ISO9660 disc images. PS3 structural inspection preserves
artifact-local metadata without creating normalized content.

The standard runtime reports separate capabilities for NES, Dolphin, and
original-Xbox normalization.

NES normalization is implemented directly by the framework. GameCube/Wii and
original-Xbox normalization require their respective external backends.

A runtime can be partially usable even when `fully_ready` is false.

## Identify a file

The complete standard composition requires:

- a platform detector;
- a release resolver;
- a structural inspector;
- a content normalizer.

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
~~~

The runnable equivalent is:

~~~text
uv run --frozen python examples/identify_release.py /path/to/game
~~~

The example performs network lookup through Playmatch and may invoke optional
external backends depending on the source format.

## Inspect the result

`IdentificationResult` retains evidence layers separately.

~~~python
if result.platform_detection.best is not None:
    print(result.platform_detection.best.platform)

if result.physical_representation is not None:
    print(result.physical_representation.format)

if result.local_metadata is not None:
    print(result.local_metadata)

if result.normalized_content is not None:
    print(result.normalized_content.hashes)

if result.canonical_match is not None:
    print(result.canonical_match.release_name)
~~~

Useful state helpers include:

- `identified`;
- `has_normalized_content`;
- `has_physical_representation`;
- `has_local_metadata`;
- `has_release_conflict`;
- `has_platform_conflict`.

These are convenience observations only. They do not change reconciliation or
selection behavior.

## Verify identification

~~~python
from rom_metadata_framework import verify_identification

verification = verify_identification(result)

print(verification.content_known_good)
print(verification.representation_known_good)
print(verification.safe_for_canonical_naming)
~~~

Physical and normalized evidence are verified independently.

A normalized known-good result can establish trust in canonical content without
claiming that the exact physical representation is known-good.

## Plan a canonical filename

Naming is based on canonical release identity, not descriptive metadata.

~~~python
from rom_metadata_framework import NamingPolicy

canonical = result.canonical_match

if canonical is not None:
    verification = verify_identification(result)

    plan = NamingPolicy().plan_rename(
        "original-file.rom",
        canonical,
        verification=verification,
    )

    print(plan.destination_name)
    print(plan.safe_to_apply)
    print(plan.operation)
~~~

The default operation is `copy`. The framework returns a plan; it does not
perform the filesystem mutation.

## Metadata enrichment

Rich provider metadata is a separate post-identification stage.

`collect_identification_metadata()` requires a `MetadataProviderCollection`
containing application-selected metadata providers.

Provider metadata remains separate from locally extracted metadata and does not
alter canonical identity, verification, or naming.

See [Metadata Selection Policy](metadata-selection-policy.md) for the
non-selection contract.

## Next references

- [Architecture](ARCHITECTURE.md)
- [Runtime Backends](runtime-backends.md)
- [Metadata Selection Policy](metadata-selection-policy.md)
