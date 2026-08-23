# rcheevos Upstream

## Project

- Project: rcheevos
- Upstream: RetroAchievements/rcheevos
- License: MIT
- Selected release: 12.4.0
- Selected revision: `2ad0b8672f68a48148620164510b963039e49eb1`
- Selected upstream branch: `master`

The upstream project recommends that integrations use `master`, which
corresponds to the latest official release, rather than the active development
branch.

## Integration boundary

The framework will not translate or reimplement rcheevos hashing logic.

Instead, an original helper program maintained by this project will call the
public rcheevos hashing API and expose a narrow machine-readable interface to
the Python framework.

The initial implementation will use these public API functions:

- `rc_hash_initialize_iterator`
- `rc_hash_generate`
- `rc_hash_destroy_iterator`
- `rc_version_string`

`rc_hash_iterate` may be exposed later if automatic console/hash candidate
enumeration becomes useful.

Deprecated `rc_hash_generate_from_file` and
`rc_hash_generate_from_buffer` APIs will not be used.

## Initial validation platform

Super Nintendo Entertainment System:

- rcheevos constant: `RC_CONSOLE_SUPER_NINTENDO`
- numeric console ID: `3`

Local validation uses independently supplied ROM files outside this repository.
No ROM images are committed, copied into test fixtures, or redistributed.

## Update policy

Changing the pinned rcheevos revision requires:

1. review of upstream release notes;
2. review of hashing-related API or behavior changes;
3. rerunning committed unit tests;
4. rerunning the local ROM validation suite;
5. updating this provenance record if the selected version changes.
