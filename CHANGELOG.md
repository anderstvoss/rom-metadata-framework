# Changelog

All notable changes to ROM Metadata Framework will be documented in this file.

The project is currently pre-1.0. No tagged public release has been declared
yet. Versioning and release expectations are documented in
`docs/release-policy.md`.

## [Unreleased]

- Add directed platform and platform-native identity selection across
  `inspect`, `identify`, `plan-rename`, `rename`, and `verify`, with soft
  preferred routing by default and hard compute-saving `--restrict` semantics.
- Add bounded restricted-identity preflight so unsupported platforms,
  unresolved native identifiers, and explicit native-ID mismatches can stop
  before whole-file hashing or unrelated provider/backend work.
- Add requested-identity matched/mismatched/unresolved evidence to
  identification output without allowing a requested identity to overwrite
  discovered identity.
- Add explicit `rom-metadata rename` execution with interactive confirmation
  and `-y` / `--yes` prompt bypass while retaining canonical verification,
  conflict, path, and collision safety requirements.
- Add guarded same-directory no-overwrite rename mutation, including symlink
  source rejection, dangling-symlink destination protection, atomic hard-link
  destination creation, and rollback handling for source-unlink failure.
- Add structured canonical rename planning through `rom-metadata plan-rename`
  and identification-aware naming using platform-native IDs, region,
  non-default revision, and true multi-disc evidence when structurally
  available.
- Improve identification output with concise title/platform/region/native-ID/
  revision/disc/format presentation plus concise and complete JSON projections.
- Preserve useful local structural identification when Playmatch is unavailable
  or has no match, and make optional normalization adaptive to physical
  catalogue evidence.
- Document Playmatch's current lack of generic platform-native-ID query support;
  requested native identity remains local routing/evidence rather than a
  provider-side release lookup primitive.

- Add bounded Nintendo Switch NSP/XCI detection and structural inspection,
  including dependency-free PFS0/HFS0 parsing, optional plaintext
  Application CNMT XML metadata, and separately provenanced ticket rights
  identifiers without introducing a Switch normalization path.
- Reject malformed/truncated Switch container extents and require
  Switch-specific NCA/content-meta structure rather than treating generic
  PFS0/HFS0 magic or filename extensions as sufficient platform evidence.

- Add bounded Xbox 360 XDVDFS/XEX2 disc detection and structural
  inspection, including title ID, media ID, executable version, and
  disc metadata without introducing an Xbox 360 normalization path.
- Add a shared bounded dependency-free XDVDFS reader with fixed-offset
  volume detection, directory-tree traversal, and bounded file-range
  reads.
- Harden original-Xbox detection to require root `default.xbe` with
  `XBEH` magic instead of treating XDVDFS recognition alone as
  sufficient platform evidence.
- Replace a corpus-derived synthetic PS3 title ID in tests with a
  neutral fixture value.

- Add bounded PlayStation 3 readable-ISO detection and structural metadata
  inspection using `PS3_DISC.SFB` and `PS3_GAME/PARAM.SFO`, including
  cross-checked title IDs, local title/version metadata, and no PS3
  normalization path.
- Extract the bounded ISO9660 reader used by PS2 into a shared internal
  implementation for reuse by PS3 while preserving PS2 behavior.

### Added

- Stable root consumer API.
- Physical-representation preservation through top-level identification.
- Local metadata extraction and provider metadata enrichment.
- Diagnostic metadata reconciliation without provider precedence.
- Explicit metadata non-selection policy.
- Runtime capability reporting and optional Dolphin/xdvdfs backend
  documentation.
- Repository packaging, distribution, and release-readiness validation.
- Runnable standard-composition examples and release-consistent package
  artifact validation.
- PlayStation 2 ISO9660 detection using root `SYSTEM.CNF` / `BOOT2`
  structural evidence.
- Non-normalizing structural inspection for physical-representation and local
  artifact metadata, with PS2 as the first default inspector.
