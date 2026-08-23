# Runtime Backends

ROM Metadata Framework can normalize some formats using optional external
command-line tools. These tools are runtime dependencies of specific adapters,
not Python package dependencies and not metadata providers.

The standard normalizer currently contains three adapters:

1. NES normalization, implemented directly by the framework;
2. GameCube/Wii normalization backed by `dolphin-tool`;
3. original-Xbox normalization backed by `xdvdfs`.

An unavailable optional backend does not disable adapters that can independently
identify and normalize the same input. The router evaluates every adapter,
preserves probe diagnostics, and selects exactly one supported normalizer.

## Backend discovery

External backends are configured by executable name or path.

By default, the framework uses:

| Capability | Backend | Default executable |
| --- | --- | --- |
| GameCube/Wii normalization | Dolphin | `dolphin-tool` |
| Original-Xbox normalization | xdvdfs | `xdvdfs` |

The backend layer resolves configured executable names through the process
`PATH`. Callers may instead supply another executable name or path through the
adapter, default-normalizer, or runtime-report configuration APIs.

Backend processes are invoked directly without a command shell. Standard
output, standard error, and the return code are captured. Backend executions
use a timeout and non-zero exits are represented explicitly as backend errors.

## Runtime capability reporting

Adapters that depend on external tools expose runtime capability information.
The standard runtime report contains:

- `nes-normalization`
- `dolphin-normalization`
- `xbox-normalization`

Each capability has one of four states:

| Status | Meaning |
| --- | --- |
| `ready` | The required capability probe completed successfully. |
| `unavailable` | The required executable could not be found. |
| `error` | The executable was found, but its capability probe failed. |
| `unknown` | A component does not expose runtime capability information. |

Executable discovery alone does not imply that a capability is operational.
An executable that is present but fails its health probe is reported as
`error`, not `ready`.

The framework-level runtime report can therefore be partially ready. For
example, NES normalization can remain ready while Dolphin and xdvdfs are
unavailable.

## Normalizer probe semantics

Runtime capability reporting describes the environment. Per-file normalizer
probing separately describes what happened when an adapter examined a source.

Probe outcomes are:

| Probe status | Meaning |
| --- | --- |
| `supported` | The adapter has positive evidence that it can safely normalize the source. |
| `unsupported` | The source is not recognized by that adapter. |
| `unsafe` | The adapter identified a condition where normalization must not proceed. |
| `backend-unavailable` | A required external backend could not be invoked because it is absent. |
| `backend-failure` | A required backend was available but probing failed operationally. |

`unsafe`, `backend-unavailable`, and `backend-failure` are terminal diagnostic
outcomes when no adapter positively supports the source.

If exactly one adapter reports `supported`, that adapter is selected even if
another optional adapter reports a terminal backend problem. This prevents a
missing unrelated backend from blocking a valid independent normalization
path.

If more than one adapter positively supports a source, routing fails as
ambiguous rather than selecting by registration order.

## Dolphin backend

The Dolphin adapter normalizes GameCube and Wii disc images through
`dolphin-tool`.

### Capability probe

Dolphin capability health is checked with:

```text
dolphin-tool header -h
```

A successful invocation marks `dolphin-normalization` as ready. This probe
checks the subcommand required by the adapter rather than relying on a generic
version command.

### File probe

For a candidate file, the adapter requests JSON disc-header information:

```text
dolphin-tool header -i <source> -j
```

The file is supported only when Dolphin returns a usable disc header containing
the required game ID and revision.

An empty JSON object is treated as an ordinary unsupported source. Invalid JSON,
an incomplete non-empty header, a timeout, or another backend failure is
reported as a backend failure instead of being treated as a format mismatch.

### Normalization

For a supported GameCube or Wii source, Dolphin reconstructs a canonical
plain-disc ISO in a temporary workspace:

```text
dolphin-tool convert \
  -u <temporary-user-directory> \
  -i <source> \
  -o <temporary-canonical-iso> \
  -f iso
```

The framework computes CRC32, MD5, SHA1, and SHA256 from the reconstructed ISO.
These normalized hashes describe canonical disc content rather than the
physical source container.

The adapter may also request a RetroAchievements-compatible hash through:

```text
dolphin-tool verify -i <source> -a rchash
```

A legacy empty or zero `rchash` response is treated as unavailable specialized
identity rather than as a normalization failure.

Dolphin header information supplies local structural evidence such as:

- GameCube/Wii platform
- Nintendo game ID
- disc revision
- region and country when present
- internal title when present
- Wii title ID when present

Container properties returned by Dolphin, such as compression method, block
size, and compression level, remain representation metadata and are kept
separate from canonical content identity.

### Temporary storage

Canonical ISO reconstruction occurs inside an automatically removed temporary
directory.

Callers may optionally provide an existing directory under which the temporary
workspace will be created. The configured directory must already exist.

Because the temporary canonical ISO can be comparable in size to the represented
disc, deployments should ensure the selected temporary filesystem has adequate
free space.

## xdvdfs backend

The Xbox adapter normalizes original-Xbox XDVDFS disc images through `xdvdfs`.

### Capability probe

xdvdfs capability health is checked with:

```text
xdvdfs --version
```

A successful invocation marks `xbox-normalization` as ready.

### File probe

Candidate files are structurally checked with:

```text
xdvdfs info <source>
```

A normal parser rejection is treated as `unsupported`, because it indicates
that the source is not a valid XDVDFS image.

Timeouts and other backend-level failures are reported as `backend-failure`.
A missing executable is reported as `backend-unavailable`.

A successful probe must explicitly report the image as valid before the adapter
claims support.

### Representation detection

The framework distinguishes two original-Xbox physical representations:

- XISO
- full-disc image

Representation detection is separate from normalized content identity. The
resulting representation metadata records a disc image backed by the XDVDFS
filesystem.

### Normalization

For a supported image, xdvdfs supplies a normalized filesystem checksum:

```text
xdvdfs checksum --silent <source>
```

The framework requires a 64-character hexadecimal checksum.

The adapter also extracts the boot executable into a temporary workspace:

```text
xdvdfs copy-out <source> default.xbe <temporary-output>
```

The framework parses the XBE certificate itself and computes SHA256 over the
extracted `default.xbe`.

The normalized Xbox content identity therefore includes specialized identifiers
for information such as:

- XDVDFS content checksum
- `default.xbe` SHA256
- Xbox title ID

Local XBE evidence can include:

- title
- title ID and formatted title ID
- alternate title IDs
- executable version
- disc number
- region mask and normalized regions
- XBE and certificate timestamps
- ratings and allowed-media masks

These locally extracted facts remain separate from provider-supplied release
metadata.

### Temporary storage

`default.xbe` is extracted into an automatically removed temporary directory.

As with Dolphin, callers may optionally provide an existing directory under
which temporary workspaces are created.

## Default normalizer configuration

The standard normalizer can be built with custom backend executables and
temporary-directory roots:

```python
from rom_metadata_framework.defaults import build_default_normalizer

normalizer = build_default_normalizer(
    dolphin_executable="dolphin-tool",
    dolphin_temporary_directory=None,
    xbox_executable="xdvdfs",
    xbox_temporary_directory=None,
)
```

Headerless NES normalization remains disabled by default because a filename
extension alone is not considered authoritative content evidence.

## Runtime inspection

A framework-level report for the standard normalizer is available through
`build_default_runtime_report`:

```python
from rom_metadata_framework.runtime import build_default_runtime_report

report = build_default_runtime_report()

for capability in report.capabilities:
    print(
        capability.name,
        capability.status,
        capability.reason,
    )
```

`fully_ready` is true only when every reported capability is explicitly ready.
A missing optional backend therefore makes the aggregate report not fully
ready, even though independently usable adapters may continue to operate.

## Installation responsibility

ROM Metadata Framework does not install or bundle Dolphin or xdvdfs.

Operators are responsible for installing compatible versions of these tools
and making the configured executables available to the framework process.
Installation method and package availability vary by operating system and
distribution.

The framework documents the command-line behavior it relies on rather than
requiring one particular packaging method.

## Failure model

The backend abstraction distinguishes:

- executable not found;
- invocation timeout;
- non-zero backend exit;
- malformed or unusable backend output;
- valid backend rejection of an unsupported source.

This distinction is intentional. A format mismatch should not masquerade as an
operational backend failure, and a broken or absent backend should not silently
masquerade as an unsupported file.

See also:

- `docs/ARCHITECTURE.md`
- `docs/THIRD_PARTY_PROVENANCE.md`
- `docs/LICENSING.md`
