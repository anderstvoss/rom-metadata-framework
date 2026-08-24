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
rom-metadata rename PATH
rom-metadata verify PATH
~~~

Every command supports `--help`.

Commands that return structured data also support `--json`.

## Directed platform and identity selection

The path-oriented commands `inspect`, `identify`, `plan-rename`, `rename`, and
`verify` accept:

~~~text
--platform PLATFORM
--identity PLATFORM:ID
--restrict
~~~

`--platform PLATFORM` is a soft platform preference by default. The standard
runtime tries components that own that platform first. If they do not recognize
the input, unrestricted handling may fall back to the ordinary platform
discovery path.

`--identity PLATFORM:ID` is a soft platform-native identity hypothesis. It
implies the platform and compares the requested ID with locally extracted
structural identity where the platform has a defined primary native identifier.
The result can be reported as matched, mismatched, or unresolved. A soft
mismatch does not rewrite the file's identity and does not prevent ordinary
discovery of the actual platform.

`--restrict` changes either selector into a hard compute-saving restriction:

- `--platform X --restrict` invokes only platform handling owned by `X`;
- `--identity X:Y --restrict` first establishes platform `X` and the local
  native identifier using bounded detection/inspection before whole-file
  hashing or provider lookup;
- a restricted platform mismatch is unresolved;
- a restricted native-ID mismatch is an explicit conflict;
- a restricted identity that cannot be established locally is unresolved.

`--restrict` without `--platform` or `--identity` is invalid usage.
Supplying both selectors is valid only when they refer to the same canonical
platform.

These selectors affect runtime routing. They do not change provider precedence,
manufacture canonical release identity, or authorize an unsafe rename.

Current primary native-identifier namespaces used for requested-identity
assessment include GameCube/Wii Game ID, PS2 product code, PS3 title ID,
original-Xbox title ID, Xbox 360 title ID, and Nintendo Switch Application ID.

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
rom-metadata inspect PATH --platform wii
rom-metadata inspect PATH --identity wii:ABCD01
rom-metadata inspect PATH --identity wii:ABCD01 --restrict
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
rom-metadata identify PATH --progress
rom-metadata identify PATH --verbose
rom-metadata identify PATH --json
rom-metadata identify PATH --hashes
rom-metadata identify PATH --json --complete
rom-metadata identify PATH --no-normalize
rom-metadata identify PATH --platform wii
rom-metadata identify PATH --identity wii:ABCD01
rom-metadata identify PATH --identity wii:ABCD01 --restrict
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

`--progress` writes a live single-line coarse-stage indicator to standard error
when attached to a terminal. The stage label changes only when the underlying
workflow actually enters a new operation, such as physical hashing, platform
detection, provider lookup, structural inspection, normalization, normalized
lookup, or evidence reconciliation. When standard error is not a terminal,
progress falls back to one line per stage rather than emitting terminal control
sequences.

`--verbose` writes timed multiline stage transitions to standard error. It is
intended for diagnosing where identification time is being spent. `--progress`
and `--verbose` are mutually exclusive.

Both modes leave normal result output on standard output. This includes
`--json`, so commands such as:

~~~text
rom-metadata identify PATH --json --progress
~~~

still emit only JSON on standard output while progress remains on standard
error.

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
rom-metadata plan-rename PATH --progress
rom-metadata plan-rename PATH --verbose
rom-metadata plan-rename PATH --json
rom-metadata plan-rename PATH --no-normalize
rom-metadata plan-rename PATH --platform wii
rom-metadata plan-rename PATH --identity wii:ABCD01 --restrict
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


## `rename`

~~~text
rom-metadata rename PATH
rom-metadata rename PATH --progress
rom-metadata rename PATH --verbose
rom-metadata rename PATH --yes
rom-metadata rename PATH --identity wii:ABCD01
rom-metadata rename PATH --identity wii:ABCD01 --restrict
rom-metadata rename PATH --no-normalize
~~~

Runs the standard identification workflow, applies catalogue-backed
verification and the structured naming policy, and, when the result is safe,
renames the existing file within its current directory.

Human output first reports the identification result and then shows the old and
new filename. Without `--yes`, the command prompts:

~~~text
Rename file? [y/N]
~~~

Only an affirmative response performs the mutation. `-y` / `--yes` bypasses
that confirmation prompt only. It does **not** bypass:

- requested-identity mismatches;
- unresolved or conflicting release evidence;
- canonical naming verification requirements;
- source-path validation;
- destination collisions;
- same-directory restrictions.

A mismatched explicit `--identity` is never treated as a request to force the
file into that identity. The current Playmatch API cannot resolve a
platform-native identifier directly into trustworthy replacement release
metadata, so the command refuses such a mismatch even with `--yes`.

If the proposed destination is the same path, the command reports that the file
is already canonical and performs no mutation.

The implementation rejects symbolic-link sources, requires a regular file,
treats an existing path or dangling symlink at the destination as occupied, and
never overwrites the destination. The guarded file operation creates the
destination with a same-directory hard link before removing the original name.
Filesystems that cannot support that operation fail rather than falling back to
an overwrite-capable rename primitive.

A successful rename returns exit code `0`. Unresolved/unsafe results return
`3`, explicit conflicts return `4`, and operational failures return `5`.

## `verify`

~~~text
rom-metadata verify PATH
rom-metadata verify PATH --progress
rom-metadata verify PATH --verbose
rom-metadata verify PATH --json
rom-metadata verify PATH --no-normalize
rom-metadata verify PATH --platform wii
rom-metadata verify PATH --identity wii:ABCD01 --restrict
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

An exact or otherwise authoritative catalogue identification does not
automatically imply `known_good`. For example, a matching record can remain
`catalogue_match` when its catalogue authority is not trusted by the current
verification policy, its record is not current when current-catalogue evidence
is required, or its verification status does not meet the accepted policy.
Such a result may identify the release successfully while still remaining
insufficient for canonical rename authorization.

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

## Progress and standard streams

`identify`, `plan-rename`, `rename`, and `verify` accept the shared progress
options:

- `--progress`: live coarse-stage progress on standard error;
- `--verbose`: timed multiline stage progress on standard error.

The options are mutually exclusive. Terminal animation is used only for
`--progress` when standard error is attached to a terminal; redirected/non-TTY
progress uses ordinary lines. Terminal outcomes distinguish successful
catalogue identification, strong local identification, catalogue
unavailability, conflicts, unresolved results, and operational failure.

`inspect` intentionally does not expose these options because its local
detection/inspection workflow is bounded and does not perform the full
hash/provider/normalization pipeline.

## JSON output

`--json` emits machine-readable JSON to standard output. Progress output remains
on standard error and does not contaminate the JSON stream.

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

`identify`, `plan-rename`, `rename`, and `verify` use the standard Playmatch
resolver and therefore may perform network requests.

Optional external normalization backends may also be invoked by those
identification-based commands when the detected source is handled by one of
those backends.

Use:

~~~text
rom-metadata capabilities
~~~

to inspect optional backend readiness before processing files.
