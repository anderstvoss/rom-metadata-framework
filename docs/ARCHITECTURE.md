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

The standard runtime combines independent NES, PlayStation 2,
PlayStation 3, Dolphin/GameCube/Wii, original-Xbox, Xbox 360, and Nintendo
Switch detectors with `CompositePlatformDetector`.

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

## PlayStation 3 readable-disc support

The default runtime includes bounded PlayStation 3 disc detection and
non-normalizing structural inspection for directly readable ISO9660 disc
images.

The PS3 path intentionally remains separate from normalized-content
identity.

Detection requires mutually consistent local disc evidence:

- a valid ISO9660 primary volume descriptor;
- root `PS3_DISC.SFB` with valid `.SFB` structure;
- `PS3_GAME/PARAM.SFO` with valid PSF/SFO structure;
- `PARAM.SFO` category `DG`;
- a valid PS3 title ID;
- agreement between the title ID recorded by `PS3_DISC.SFB` and
  `PARAM.SFO`.

The structural inspector may additionally preserve:

- ISO volume identifier;
- PS3 title ID;
- locally encoded title;
- application version;
- game/version metadata;
- required PS3 system version;
- bootable state;
- presence of `PS3_GAME/USRDIR/EBOOT.BIN`.

This evidence is artifact-local. It does not cause provider lookup and it
does not manufacture normalized content hashes.

The standard PS3 implementation currently supports directly readable
ISO9660 representations only. Encrypted/raw PS3 disc representations are
not currently decoded or normalized by the framework.

There is currently no PS3 normalizer and no PS3 normalization runtime
capability.

## Xbox 360 readable-disc support

The default runtime includes bounded Xbox 360 disc detection and
non-normalizing structural inspection for directly readable XDVDFS game
partitions.

Xbox 360 detection is generation-specific rather than filesystem-only.
XDVDFS is shared by original Xbox and Xbox 360 software, so the
filesystem alone is not sufficient evidence for either platform.

Xbox 360 detection requires:

- a valid XDVDFS volume descriptor at a bounded known game-partition
  offset;
- a valid bounded root directory;
- root `default.xex`;
- `XEX2` executable magic;
- a valid XEX2 Execution ID optional header;
- internally consistent disc-number and disc-count values.

The structural inspector preserves artifact-local evidence including:

- XDVDFS partition and representation information;
- Xbox 360 title ID;
- media ID;
- executable version and base version;
- disc number and disc count;
- XEX platform and executable-type fields;
- root `default.xex` structural location and size.

The original-Xbox detector separately requires root `default.xbe` with
valid `XBEH` magic. A valid XDVDFS filesystem therefore no longer
implicitly identifies an image as original Xbox.

Xbox 360 structural evidence does not create normalized content identity
and does not cause normalized provider lookup.

There is currently no Xbox 360 normalizer and no Xbox 360 normalization
runtime capability. No RetroAchievements/rcheevos Xbox 360 backend
mapping is currently registered.

## Nintendo Switch container support

The default runtime includes bounded, dependency-free detection and
non-normalizing structural inspection for Nintendo Switch NSP package
containers and XCI game-card images.

Switch detection is representation-aware:

- NSP support requires a valid bounded PFS0 container with at least one
  NCA entry and at least one `.cnmt.nca` content-meta NCA.
- XCI support requires valid `HEAD` game-card header magic, a bounded
  header-derived root HFS0 filesystem, a `secure` HFS0 partition, and
  NCA/content-meta entries in that secure partition.
- File extensions and filenames alone are not sufficient platform
  evidence.
- Malformed or truncated PFS0/HFS0 extents are rejected rather than
  accepted from partial structure.

The outer PFS0/HFS0 tables and XCI game-card header are plaintext and can
be inspected without Nintendo Switch keys. NCA headers and most metadata
within NCA content remain encrypted and are not decoded by the framework.

Some NSP packages contain a plaintext `.cnmt.xml` sidecar. When present,
bounded XML parsing may preserve root `ContentMeta` facts such as:

- application title ID when the root content-meta type is `Application`;
- application version;
- required system version;
- patch title ID.

Nested content IDs in CNMT XML are content identifiers and are not treated
as application title IDs.

Ticket filenames may expose a 128-bit rights ID. The first 64 bits are
preserved separately as a rights title ID. Rights title IDs are local
rights evidence only and are not automatically promoted to application
identity: for example, an XCI may carry a patch rights ID rather than the
base application ID.

Nintendo Switch structural inspection may therefore preserve:

- container representation (`pfs0` package or `xci` game-card image);
- NCA and content-meta-NCA counts;
- optional application ID and version from plaintext Application CNMT XML;
- optional required-system-version and patch-ID metadata;
- ticket rights IDs and rights title IDs with distinct provenance.

Packages without plaintext CNMT XML can still be detected and inspected,
but application identity is intentionally left unspecified unless it can
be established from supported plaintext structural metadata.

Switch structural evidence does not create normalized content identity and
does not trigger normalized provider lookup.

There is currently no Nintendo Switch normalizer, no Nintendo Switch
normalization runtime capability, and no RetroAchievements/rcheevos
Nintendo Switch backend mapping.

## Specialist integrity verification

Catalogue-backed release verification and specialist artifact-integrity
verification are separate trust layers.

`verify_release()` evaluates release/catalogue evidence such as trusted
No-Intro or Redump content matches. It does not inspect optical sectors,
validate platform signatures, consume IRD records, or otherwise establish
platform-specific media integrity.

Specialist validation is represented separately by the `IntegrityVerifier`
contract. An integrity verifier operates on the physical artifact and returns
an `IntegrityReport` containing platform-specific evidence and one normalized
outcome:

- `verified`: the verifier positively established the integrity property it
  evaluates;
- `failed`: the verifier positively established that the artifact violates
  that integrity property;
- `inconclusive`: verification ran but could not establish either validity or
  failure.

An `inconclusive` result is not evidence that an artifact is corrupt.

`CompositeIntegrityVerifier` conservatively routes an artifact to exactly one
applicable specialist verifier. Multiple positive claims are ambiguous, while
backend failures are surfaced when no independent verifier can positively
handle the artifact.

The default runtime currently registers no specialist integrity verifiers.
This contract is groundwork for future implementations such as optical-disc
sector validation, IRD-based validation, or platform cryptographic/signature
checks.

Specialist integrity results do not automatically alter canonical release
identity, provider metadata, normalized-content identity, or catalogue-backed
verification. Any future policy combining these trust layers must be explicit.
