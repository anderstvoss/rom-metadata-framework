# ROM Metadata Framework

A Linux-oriented framework for identifying ROM and disc-image contents and
resolving those identities into game metadata.

The project separates two functions:

1. platform- and format-specific identification;
2. metadata resolution from normalized identity information.

Identification adapters may extract values such as hashes, serial numbers,
product codes, title IDs, and media metadata.

Metadata resolvers consume that normalized identity and query independent
metadata sources.

## Design goals

- Keep platform-specific identification behind modular adapters.
- Keep metadata providers independent from image parsing.
- Support implementations derived from existing emulator or utility projects
  only when their licenses permit the intended use.
- Preserve explicit upstream attribution and provenance for derived code.
- Allow external-tool adapters where directly incorporating upstream code would
  create undesirable licensing coupling.
- Use synthetic or freely redistributable fixtures for public tests.
- Prevent ROM images, credentials, private infrastructure details, and local
  development data from entering public repository history.

## Runtime backends

The framework includes built-in NES normalization and optional external-tool
normalizers for GameCube/Wii and original-Xbox disc images.

The standard runtime expects `dolphin-tool` for GameCube/Wii normalization and
`xdvdfs` for original-Xbox XDVDFS normalization when those capabilities are
used. Missing optional backends are reported explicitly and do not prevent an
independent adapter from handling a supported source.

See [Runtime Backends](docs/runtime-backends.md) for executable discovery,
capability reporting, probe semantics, temporary storage, and the exact backend
operations used by the framework.

## Status

The framework currently provides physical identity hashing, platform evidence,
canonical-content normalization, release reconciliation, local and provider
metadata evidence, verification, naming policy, runtime capability reporting,
and an explicit consumer-facing Python API.

Platform and format support remains intentionally modular and incomplete.
