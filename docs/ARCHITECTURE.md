# Architecture

## Purpose

ROM Metadata Framework separates the identity of a physical ROM or disc image
from the identity of the game release it represents.

The framework deliberately keeps these concepts distinct:

1. physical-file identity;
2. platform evidence;
3. physical representation;
4. normalized or canonical content;
5. canonical game/release identity;
6. local structural metadata;
7. provider-supplied release metadata;
8. verification;
9. naming and file-operation policy.

This separation prevents metadata enrichment, container details, or provider
ordering from silently changing identity or trust decisions.

## Identification pipeline

The high-level identification flow is:

~~~text
physical file
   |
   +--> generic whole-file hashes ----------------------+
   |                                                    |
   +--> platform detectors                              |
   |                                                    |
   +--> physical provider lookup -----------------------+
   |                                                    |
   +--> optional structural inspector                   |
   |        |                                           |
   |        +--> physical representation                |
   |        +--> local structural metadata              |
   |                                                    |
   +--> optional content normalizer                     |
            |                                           |
            +--> physical representation                |
            +--> local structural metadata              |
            +--> normalized content hashes              |
                         |                               |
                         +--> normalized provider lookup+
                                                         |
                                                         v
                                              release reconciliation
                                                         |
                                                         v
                                              canonical release identity
~~~

The physical lookup is intentionally performed before structural inspection
or normalization.

Neither structural inspection nor normalization is therefore a prerequisite
for physical provider lookup. Structural inspection extracts representation or
artifact-local metadata without creating canonical content. Normalization is an
additional evidence path used when a format can be reduced to a more canonical
content representation.

## Physical-file identity

`RomIdentity` represents facts about the exact source file presented to the
framework.

Its generic CRC32, MD5, SHA1, and SHA256 values are hashes of the physical file
bytes.

Physical hashes must not be replaced with normalized hashes or specialized
platform identifiers.

A provider may identify a release directly from physical-file identity before
any normalization occurs.

## Platform detection

Platform detection is independent from release lookup.

A `PlatformDetector` returns one or more `PlatformCandidate` values, each with
confidence and provenance-bearing `PlatformEvidence`.

The standard runtime combines independent NES, Dolphin, and original-Xbox
detectors with `CompositePlatformDetector`.

When several detectors identify the same canonical platform, their evidence is
combined and the highest confidence is retained. Distinct equally ranked
platform candidates remain ambiguous.

Provider platform evidence is reconciled with local detector evidence later in
the identification pipeline.

## Physical representation

`RepresentationIdentity` describes how content is physically represented by the
source file.

Examples include:

- an iNES or NES 2.0 cartridge representation;
- an RVZ or ISO disc-image representation;
- an original-Xbox XISO or full-disc representation.

Representation is deliberately separate from normalized content. Converting or
reconstructing canonical content does not change what representation the
original source used.

## Normalized content

`NormalizedContentIdentity` represents canonicalized content derived from the
physical source.

Depending on platform and format, normalization may:

- remove representation-specific bytes;
- reconstruct a canonical disc image;
- derive a filesystem-level content checksum;
- preserve specialized platform identifiers.

The normalized identity has its own hashes and identifiers. These must not
replace the physical hashes stored in `RomIdentity`.

The standard normalizer currently supports:

- NES directly in Python;
- GameCube/Wii using `dolphin-tool`;
- original Xbox using `xdvdfs`.

See [Runtime Backends](runtime-backends.md) for backend contracts and failure
semantics.

## Structural inspection and local metadata

Some artifact-local evidence does not require or imply content normalization.

A `StructuralInspector` may return a `RepresentationIdentity`,
`LocalContentMetadata`, or both without producing a
`NormalizedContentIdentity`. Structural inspection therefore does not create
normalized hashes and does not initiate normalized provider lookup.

Normalization may also return representation and local-metadata evidence when
extracting those values is naturally part of the normalization process.
`identify_file()` preserves evidence from both paths. If an inspector and a
normalizer independently return the same structural evidence type, the values
must agree; conflicting evidence is rejected rather than silently overwritten.

`LocalContentMetadata` represents trustworthy facts extracted directly from the
represented artifact, such as:

- internal titles;
- product or title identifiers;
- revisions;
- regions;
- languages;
- executable versions;
- disc numbering;
- hardware fields;
- build or certificate timestamps.

Local metadata is not provider metadata.

It does not participate in provider ordering, canonical release selection,
verification, or naming unless a separate policy explicitly defines such use.

## Release lookup and reconciliation

Release lookup has two independent opportunities:

1. lookup from physical-file identity;
2. lookup from normalized-content identity, when normalization succeeds.

`identify_file()` preserves both observations as `physical_match` and
`normalized_match`.

`ReleaseReconciliation` compares them.

Compatible observations may yield a canonical release identity. Conflicting
release or platform evidence blocks implicit canonical selection rather than
silently choosing one path.

This design allows exact physical representations to match catalogues when
possible while retaining a normalized fallback for alternate representations.

## Canonical release identity

`CanonicalReleaseIdentity` is provider-independent release identity.

It contains the release name, canonical platform, source identifiers,
identification evidence, catalogue evidence, and conflicts.

It is distinct from descriptive release metadata.

A release may therefore be identified even when rich provider metadata has not
yet been collected.

## Provider metadata enrichment

Metadata enrichment begins only after canonical release reconciliation.

`collect_identification_metadata()` receives an `IdentificationResult` and a
`MetadataProviderCollection`.

Each provider receives the already selected canonical release identity.

Provider results remain independent `MetadataProviderResult` observations.
Registration order is execution order only and does not define precedence.

Local metadata and provider-supplied `ReleaseMetadata` remain structurally
separate.

See [Metadata Selection Policy](metadata-selection-policy.md).

## Metadata reconciliation

`MetadataReconciliationReport` compares fields whose local and provider
semantics are sufficiently compatible.

Current comparisons include:

- titles;
- developers;
- publishers;
- regions;
- languages;
- player counts;
- multiplayer features;
- identifiers with matching normalized namespaces and exact opaque values.

Reconciliation is diagnostic only.

It does not:

- select a preferred metadata value;
- rank providers;
- alter canonical identity;
- alter verification;
- alter naming.

## Verification

Verification is derived from canonical release and catalogue evidence.

The default policy recognizes trusted catalogue authorities and requires strong
content evidence before establishing known-good status.

Physical and normalized matches are verified independently.

This allows the framework to distinguish:

- trust in the exact physical representation;
- trust in normalized canonical content.

Known-bad evidence and unresolved conflicts block safe canonical naming.

## Naming and file operations

`NamingPolicy` derives filenames from `CanonicalReleaseIdentity`, not from
provider metadata or local metadata.

`plan_rename()` is non-mutating and returns a `RenamePlan`.

The default operation is `copy`.

Replacing the original file is an explicit opt-in operation.

A canonical name is considered safe only when identification verification
supports it and unresolved conflicts are absent.

## Runtime composition

The standard application composition is built from one
`DefaultRuntimeConfig`.

~~~python
from rom_metadata_framework.defaults import (
    DefaultRuntimeConfig,
    build_default_detector,
    build_default_inspector,
    build_default_normalizer,
)
from rom_metadata_framework.playmatch import PlaymatchResolver

config = DefaultRuntimeConfig()

detector = build_default_detector(config)
inspector = build_default_inspector(config)
normalizer = build_default_normalizer(config)
resolver = PlaymatchResolver()
~~~

Detector, structural-inspector, and normalizer construction use the same
`DefaultRuntimeConfig`. The default structural inspector is dependency-free;
backend executable configuration remains relevant to Dolphin and xdvdfs
detection and normalization.

Runtime capability reporting is separately available through
`build_default_runtime_report()`.

## Error boundaries

The framework distinguishes contract violations from operational failures.

Examples include:

- backend unavailable;
- backend timeout or execution failure;
- malformed backend response;
- unsupported source format;
- unsafe normalization;
- invalid provider result;
- invalid normalizer result.

An unavailable optional backend must not prevent another independent adapter
from positively handling a source.

## Public API boundary

The stable consumer-facing façade is exported from `rom_metadata_framework`.

Concrete backend adapters, provider implementations, default composition
factories, and lower-level routing helpers remain available from their defining
modules but are not currently part of the root stable API.

This lets the project refine application composition before committing every
implementation class to long-term root-level compatibility.

## Test and provenance boundaries

Public tests use synthetic, original, or freely redistributable fixtures.

Commercial ROMs, disc images, extracted copyrighted binaries, credentials,
private infrastructure details, and local validation corpora must not enter
repository history.

Third-party integrations must preserve provenance and licensing requirements.
See:

- [Licensing Policy](LICENSING.md)
- [Third-Party Provenance Policy](THIRD_PARTY_PROVENANCE.md)
