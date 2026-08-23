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

## Status

Repository bootstrap and public-development sanitation are in progress.

No emulator-derived implementation code is currently included.
