# Provider and Platform Coverage

This document records how provider/platform mappings relate to the ROM Metadata
Framework's canonical platform registry and standard runtime.

Provider registration, runtime platform support, and release identification are
separate concerns.

A provider mapping does **not** imply that the standard runtime can detect,
inspect, normalize, or verify integrity for that platform. Likewise, a platform
may have useful runtime support without a mapping for a particular provider or
specialized hashing backend.

## Default release-identification provider

The installed `rom-metadata identify` and `rom-metadata verify` workflows use
Playmatch as their standard release resolver.

The identification pipeline performs physical-file provider lookup before
optional structural inspection and normalization. When a normalizer produces a
canonical `NormalizedContentIdentity`, a second provider lookup may be
performed using that normalized content.

Playmatch is therefore a release/catalogue resolver. It is not the framework's
platform registry and does not define canonical framework platform names.

## Playmatch native-identifier lookup limitation

The current Playmatch v2 API used by this project does not expose a generic
request path that accepts platform-native identifiers such as a PS2 product
code, Wii/GameCube Game ID, PS3 title ID, Xbox title ID, Xbox 360 title/media
ID, or Nintendo Switch Application ID and resolves that value directly to a
candidate release.

Some Playmatch response objects may contain serial/native-identifier data, but
that is returned evidence rather than a supported native-ID query input.

Consequently, `--identity PLATFORM:ID` is implemented as a local routing and
evidence hypothesis:

- the platform is preferred first;
- locally extracted native identity is compared when available;
- unrestricted workflows may fall back to normal discovery;
- restricted workflows can reject a mismatch before whole-file hashing or
  provider lookup.

The framework must not substitute fuzzy title search for native-ID resolution,
must not assume Playmatch game/file UUIDs are platform-native IDs, and must not
treat a mismatched requested identity as trusted replacement metadata.

This limitation is particularly important to executable rename behavior:
`--yes` confirms an otherwise-safe rename but cannot force a file to a
mismatched requested identity.

## Playmatch platform-name reconciliation

Playmatch returns textual platform display names.

At the Playmatch boundary, the framework canonicalizes provider platform names
conservatively:

1. try the complete provider string against the canonical platform registry and
   aliases;
2. if that fails and the provider value contains one exact `" - "` separator,
   try the suffix after that separator;
3. if the suffix is also unknown, preserve the original provider-defined name
   rather than guessing.

This allows catalogue-style names such as:

- `Nintendo - NES`;
- `Sony - PlayStation 2`;
- `Microsoft - Xbox 360`;

to reconcile with canonical framework identifiers when a known alias exists.

The original Playmatch platform text is preserved in identification evidence as
`provider_platform`, even when the normalized platform field uses a canonical
framework identifier.

Local detector evidence and provider platform evidence are reconciled later.
Provider naming does not silently overwrite contradictory local platform
evidence.

## RetroAchievements / rcheevos

`rcheevos` is a specialized platform-aware hashing adapter.

It is distinct from the default Playmatch release-identification workflow.
A registered rcheevos mapping means the framework knows which rcheevos console
identifier corresponds to a canonical framework platform. It does not mean:

- rcheevos is queried automatically by `identify`;
- the standard runtime detects that platform;
- the platform has a structural inspector;
- the platform has a canonical normalizer;
- or the platform has specialist integrity verification.

Current mappings are:

| Platform | Canonical ID | rcheevos console ID | Standard runtime |
| --- | --- | ---: | --- |
| Super Nintendo Entertainment System | `snes` | 3 | Registered only |
| Sega Genesis / Mega Drive | `genesis` | 1 | Registered only |
| Nintendo 64 | `n64` | 2 | Registered only |
| Game Boy | `gb` | 4 | Registered only |
| Game Boy Advance | `gba` | 5 | Registered only |
| Game Boy Color | `gbc` | 6 | Registered only |
| Nintendo Entertainment System | `nes` | 7 | Supported |
| PlayStation | `psx` | 12 | Registered only |
| Nintendo GameCube | `gc` | 16 | Supported |
| Nintendo DS | `nds` | 18 | Registered only |
| Wii | `wii` | 19 | Supported |
| PlayStation 2 | `ps2` | 21 | Supported |
| Xbox | `xbox` | 22 | Supported |
| PlayStation Portable | `psp` | 41 | Registered only |

The canonical registry currently also contains three standard-runtime-supported
platforms with **no registered rcheevos mapping**:

| Platform | Canonical ID | Detection | Inspection | Normalization |
| --- | --- | --- | --- | --- |
| PlayStation 3 | `ps3` | Built in | Built in | None |
| Xbox 360 | `xbox360` | Built in | Built in | None |
| Nintendo Switch | `switch` | Built in | Built in | None |

These absences are intentional. The framework must not invent backend console
identifiers or infer rcheevos support from its own runtime implementation.

If upstream/backend coverage changes later, add a mapping only after verifying
the backend identifier and adding corresponding tests.

## Runtime support matrix ownership

Standard runtime implementation state is reported by:

~~~text
rom-metadata platforms
~~~

The support inventory independently tracks:

- detection;
- structural inspection;
- normalization;
- specialist integrity verification;
- rcheevos mapping presence.

The support inventory is checked against the actual default runtime by
`default_support_drift()`.

Runtime component construction remains explicit in `defaults.py`. Component to
platform ownership is declared in the single private
`_DEFAULT_COMPONENT_PLATFORMS` table in `support.py`.

This separation keeps configuration-bearing builders explicit while reducing
the number of parallel ownership declarations that must be maintained when a
new platform component is added.

## Adding or changing provider coverage

When adding a provider/backend mapping:

1. use the canonical framework platform identifier;
2. verify the backend identifier from an authoritative upstream source;
3. add the mapping to `BACKEND_PLATFORM_MAPPINGS`;
4. add mapping and alias tests;
5. do not change runtime implementation status solely because a provider
   mapping exists;
6. update this document when the public coverage matrix changes.

When adding runtime platform support, follow
[Adding a Platform](adding-a-platform.md). Provider coverage should be evaluated
independently rather than assumed.
