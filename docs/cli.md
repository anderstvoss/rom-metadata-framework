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
rom-metadata plan-rename PATH
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
rom-metadata identify PATH --hashes
rom-metadata identify PATH --json --complete
rom-metadata identify PATH --no-normalize
~~~

Runs the standard release-identification workflow.

Unlike `inspect`, `identify`:

1. computes generic hashes of the entire physical file;
2. performs physical release lookup through Playmatch;
3. performs platform detection;
4. performs structural inspection;
5. performs canonical-content normalization when useful and supported unless
   `--no-normalize` is supplied;
6. performs normalized-content provider lookup when normalization produces a
   canonical content identity;
7. reconciles physical, normalized, and platform evidence.

Normalization is adaptive. An authoritative physical-file catalogue match that
agrees with local platform evidence can skip a more expensive normalized-content
pass. Weak or missing physical matches, conflicting platform evidence, or other
cases requiring normalized evidence may still perform normalization.

Because whole-file hashing is part of this command, runtime cost scales with
file size.

The default text output is intentionally concise. Available fields may include:

~~~text
Title:      Example Game
Platform:   Wii
Region:     USA
Game ID:    ABCD01
Revision:   2
Disc:       1 / 2
Format:     RVZ
~~~

Unavailable fields are omitted. Revision zero/default revision is not shown,
and disc position is shown only when the artifact provides true multi-disc
evidence.

For user-facing `Region`, a specific country value is preferred when the
artifact exposes one. Broader representation or video-system region values such
as `NTSC-U` remain available in complete diagnostic metadata.

When a catalogue provider does not supply a distinct canonical title, `Title`
falls back to that provider's release name. The CLI does not heuristically strip
region, language, revision, or other parenthetical qualifiers from provider
release names.

Platform-native identifier labels depend on the platform. Current examples
include `Game ID`, `Product Code`, `Title ID`, and `Application ID`.

`Format` describes the physical source file format where it can be determined
from the source filename. Representation details such as ISO9660 or XGD remain
available in the complete diagnostic JSON rather than replacing the user-facing
physical format.

`--hashes` adds available hash details to text output. Physical-file hashes and
represented-content hashes are labeled separately. For example, compressed
GameCube/Wii sources may expose:

~~~text
Physical file hashes:
  SHA256: ...

Disc hashes:
  CRC32: ...
  MD5: ...
  SHA1: ...
~~~

The default `--json` output is a concise machine-readable identification result.
It includes available hashes automatically, so `--hashes` has no additional
effect when combined with `--json`. Fields that are unavailable are generally
omitted.

The concise JSON may include:

- identification `status`;
- title and `title_source`;
- canonical platform ID and display name;
- region;
- one preferred platform-native identifier;
- revision and multi-disc position when meaningful;
- physical source format;
- available physical and represented-content hashes;
- provider lookup status.

`--complete --json` emits the full diagnostic identification projection,
including physical identity, platform-detection evidence, structural metadata,
representation identity, physical and normalized provider matches, normalized
content, and reconciliation state.

`--complete` requires `--json`.

`--no-normalize` disables canonical-content normalization and normalized
provider lookup. Physical hashing and physical Playmatch lookup still occur.

A catalogue match is not required for every successful identification. Strong
local structural identification can return success even when the catalogue
provider is unavailable or has no match. Probable or unresolved local evidence
continues to use the unresolved exit status.

## `plan-rename`

~~~text
rom-metadata plan-rename PATH
rom-metadata plan-rename PATH --json
rom-metadata plan-rename PATH --no-normalize
~~~

Runs the standard identification workflow and produces a proposed canonical
filename using the structured naming policy.

`plan-rename` is deliberately non-mutating. It does not copy, rename, move,
replace, or delete the source file. The returned `operation` field describes
the naming plan's default future file-operation policy; `copy` does not mean
that this command performs a copy.

The command emits a filename rather than a destination filesystem path. The
source file's existing extension is preserved.

A canonical release match is required before a filename can be proposed.
Artifact-local identifiers, region, revision, and disc evidence are incorporated
only under the structured naming rules documented in
[Architecture](ARCHITECTURE.md).

Human output includes the proposed filename, planned operation, whether the plan
is safe to apply, and any explicit conflicts.

The concise JSON `status` field uses:

- `safe`: the canonical naming safety policy is satisfied;
- `unsafe`: a filename can be proposed, but verification is not strong enough
  to authorize canonical naming;
- `conflict`: known-bad or conflicting evidence prevents safe canonical naming;
- `unresolved`: no canonical release was resolved, so no filename can be
  proposed.

`safe` returns exit code `0`. `unsafe` and `unresolved` return code `3`.
`conflict` returns code `4`. Operational failures continue to return code `5`.

`--no-normalize` has the same meaning as for `identify`: it disables
canonical-content normalization and normalized provider lookup while retaining
physical hashing and provider lookup.

There are intentionally no `--copy`, `--replace`, or filesystem-mutation
options in this command.

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
