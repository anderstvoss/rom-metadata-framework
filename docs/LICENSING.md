# Licensing Policy

## Core framework license

Original project code is licensed under the MIT License.

This includes original code for:

- command-line interfaces;
- normalized identity models;
- adapter discovery;
- metadata resolver interfaces;
- orchestration;
- configuration;
- original platform parsers;
- original tests;
- synthetic fixtures.

## Integration preference

Platform-specific functionality should be implemented in this order of
preference:

1. original implementation from documented formats or specifications;
2. permissively licensed library;
3. independently installed external tool;
4. third-party-derived source only when necessary and explicitly reviewed.

Vendoring emulator or utility source code is not the default integration
strategy.

## External tools

The framework may invoke independently installed external executables.

Examples may include emulators, disc-image utilities, or platform-specific
inspection tools.

When an external executable is used:

- this repository does not claim ownership of that executable;
- the executable remains governed by its own upstream license;
- the executable should not be redistributed by this project unless separately
  reviewed and explicitly permitted;
- the adapter code written by this project remains MIT-licensed unless it
  contains third-party-derived code;
- the upstream project and license must still be credited.

## GPL tools

GPL-licensed emulator or utility functionality should normally be integrated as
an independently installed external executable rather than by copying or
linking its source into the MIT-licensed framework.

The framework adapter may invoke the executable and parse its output.

Any future decision to incorporate or link GPL-derived code must be reviewed
separately and must preserve the applicable GPL requirements.

## Permissively licensed libraries

Permissively licensed dependencies may be linked or incorporated when their
licenses are compatible with MIT distribution and their required notices are
preserved.

Examples include MIT and BSD-family licensed libraries.

Each dependency must still be documented.

## Third-party-derived source

Code copied, translated, adapted, or substantially derived from another
project must not be introduced casually.

Before such code is committed:

- identify the exact upstream project;
- identify the source revision;
- identify the applicable license;
- verify compatibility with the intended distribution;
- preserve required notices;
- record modifications;
- document why an external-tool or original implementation was insufficient.

Third-party-derived source may require a license different from the MIT license
used by the framework core.

## Adapter provenance

Every adapter that depends materially on another project must document:

- upstream project;
- upstream repository;
- supported upstream versions;
- upstream license;
- integration method;
- whether upstream code is redistributed;
- whether the dependency is required or optional.

This applies even when the dependency is only an external executable.

## External dependency credit

User-facing documentation should credit external projects that materially
provide identification, parsing, hashing, conversion, or metadata capability.

Formal license notices must be preserved where required.

## Test data

Public tests may use:

- synthetic fixtures;
- original fixtures created for this project;
- freely redistributable fixtures with documented provenance.

Commercial ROMs, disc images, executables, firmware, encryption keys, private
keys, or extracted copyrighted game assets must not be committed.

## Review rule

No new external dependency or third-party-derived implementation should be
merged until its license, integration method, provenance, and redistribution
requirements have been reviewed.
