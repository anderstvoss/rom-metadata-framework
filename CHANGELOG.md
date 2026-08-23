# Changelog

All notable changes to ROM Metadata Framework will be documented in this file.

The project is currently pre-1.0. No tagged public release has been declared
yet. Versioning and release expectations are documented in
`docs/release-policy.md`.

## [Unreleased]

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
