# Command-Line Interface

ROM Metadata Framework installs the `rom-metadata` command.

The CLI exposes the framework's standard runtime composition for support
inspection, local structural inspection, release identification, and
catalogue-backed verification.

## Commands

~~~text
rom-metadata platforms
rom-metadata capabilities
rom-metadata inspect PATH
rom-metadata identify PATH
rom-metadata verify PATH
~~~

Every command supports `--help`.

Commands that return structured data also support `--json`.

## `platforms`

~~~text
rom-metadata platforms
rom-metadata platforms --json
~~~

Shows every registered canonical platform and its current implementation state.

Canonical platform identifiers intentionally follow common ROM/emulation
filesystem slugs such as `ps3`, `gc`, `gba`, `nds`, `xbox360`, and `switch`.
The platform inventory also exposes a human-readable display name and
manufacturer separately from that machine-facing identifier.

The output distinguishes:

- `supported`: the standard runtime currently has at least one operational
  detector, structural inspector, normalizer, or specialist integrity verifier
  for the platform;
- `registered`: the platform exists in the canonical registry but the standard
  runtime does not currently implement platform handling.

Capability columns distinguish:

- `built-in`: implemented directly by the Python framework;
- `external`: implemented through an optional external backend;
- `none`: not currently implemented in the standard runtime.

`INTEGRITY` reports specialist physical-artifact/media verification support.
It is distinct from the catalogue-backed `verify` command.

`RCHEEVOS_MAP` indicates whether a RetroAchievements/rcheevos platform mapping
is registered. It does not by itself mean the platform has standard detector,
inspection, normalization, or integrity support.

## `capabilities`

~~~text
rom-metadata capabilities
rom-metadata capabilities --json
~~~

Reports runtime readiness of optional normalization capabilities.

A platform may still support built-in detection or structural inspection when
an unrelated optional backend is unavailable.

See [Runtime Backends](runtime-backends.md) for backend discovery and failure
semantics.

## `inspect`

~~~text
rom-metadata inspect PATH
rom-metadata inspect PATH --json
~~~

Performs bounded local platform detection and structural inspection.

`inspect` is deliberately local:

- it does not compute whole-file hashes;
- it does not query Playmatch or another network provider;
- it does not perform canonical-content normalization;
- platform detectors and structural inspectors are expected to use bounded or
  random-access reads rather than sequentially scanning large disc images.

This is the preferred command when the goal is to inspect container,
filesystem, representation, or artifact-local metadata without performing
release lookup.

## `identify`

~~~text
rom-metadata identify PATH
rom-metadata identify PATH --json
rom-metadata identify PATH --no-normalize
~~~

Runs the standard release-identification workflow.

Unlike `inspect`, `identify`:

1. computes generic hashes of the entire physical file;
2. performs physical release lookup through Playmatch;
3. performs platform detection;
4. performs structural inspection;
5. performs canonical-content normalization where supported unless
   `--no-normalize` is supplied;
6. performs normalized-content provider lookup when normalization produces a
   canonical content identity;
7. reconciles physical, normalized, and platform evidence.

Because whole-file hashing is part of this command, runtime cost scales with
file size.

`--no-normalize` disables canonical-content normalization and normalized
provider lookup. Physical hashing and physical Playmatch lookup still occur.

## `verify`

~~~text
rom-metadata verify PATH
rom-metadata verify PATH --json
rom-metadata verify PATH --no-normalize
~~~

Runs the same standard identification workflow and then applies the framework's
catalogue-backed release verification policy.

Current normalized verification statuses include:

- `known_good`;
- `known_bad`;
- `catalogue_match`;
- `conflict`;
- `probable`;
- `unknown`.

The current policy can establish `known_good` from accepted strong content
matches against trusted catalogue authorities such as No-Intro or Redump,
subject to catalogue evidence and policy requirements.

This command is not a specialist cryptographic or media-integrity verifier.
For example, it does not currently perform platform-specific optical-disc
sector validation, IRD verification, Nintendo signature verification, or
equivalent deep integrity analysis.

## Exit codes

The public CLI uses these exit codes:

| Code | Meaning |
| ---: | --- |
| `0` | Requested operation completed with a successful/resolved result |
| `2` | Invalid command-line usage reported by `argparse` |
| `3` | Operation completed, but the requested result remains unresolved or inconclusive |
| `4` | Conflicting evidence, known-bad verification, or another explicit conflict result |
| `5` | Operational, input, provider, I/O, or framework-contract failure |

Examples of code `3` include an unsupported local structural inspection,
an unresolved release identity, or a verification result that is not strong
enough to be classified `known_good` or conflict/known-bad.

## JSON output

`--json` emits machine-readable JSON to standard output.

The path-oriented commands use explicit CLI projection code rather than
automatically serializing internal dataclasses. This prevents an internal model
field from automatically becoming part of the command-line data format.

The CLI is still pre-1.0. During the `0.x` series, JSON field names and nesting
should be treated as provisional and may change in a documented minor release.
Consumers that automate against JSON output should pin the framework version
and review release notes before upgrading.

Error results emitted with `--json` contain an `error` identifier and relevant
context such as the source path, provider, or error message.

## Network and backend behavior

`platforms`, `capabilities`, and `inspect` do not perform Playmatch release
lookup.

`identify` and `verify` use the standard Playmatch resolver and therefore may
perform network requests.

Optional external normalization backends may also be invoked by `identify` and
`verify` when the detected source is handled by one of those backends.

Use:

~~~text
rom-metadata capabilities
~~~

to inspect optional backend readiness before processing files.
