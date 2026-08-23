# Release Policy

## Version source

The project version is declared in `pyproject.toml`.

Release tags use the form `vMAJOR.MINOR.PATCH` and must match the package
version exactly.

## Versioning

ROM Metadata Framework follows Semantic Versioning.

While the project remains below 1.0:

- patch releases contain compatible fixes, documentation, and packaging
  corrections;
- minor releases may add features and may make deliberate public API changes
  that require migration;
- incompatible changes to the stable root API must be documented explicitly in
  the changelog and release notes.

After 1.0, incompatible public API changes require a major-version increment.

Internal modules that are intentionally excluded from the stable root façade do
not receive the same compatibility guarantee.

## Release contents

A release candidate must satisfy all of the following:

1. the full test suite passes;
2. Ruff passes;
3. repository sanitation and secret scans pass;
4. the package builds successfully as both wheel and source distribution;
5. the built wheel installs and imports in an isolated environment;
6. package contents match the documented distribution boundary;
7. supported Python versions pass continuous integration;
8. the changelog describes user-visible changes;
9. public API changes are reflected in the explicit export contract tests;
10. third-party provenance and licensing records are current.

## Distribution boundary

The wheel contains the Python framework and applicable license/notice material.

The source distribution may additionally contain public documentation and
repository guidance required to understand and build the released source.

External backend executables, helper binaries, commercial game content, private
validation data, local machine configuration, and credentials are not release
artifacts.

## Publication

No automated package-index publication workflow is currently part of the
repository. Adding publication credentials or trusted-publishing configuration
must be treated as a separate security-sensitive change.

A release should not be tagged until the exact artifacts intended for
publication have passed the package-artifact validation.
