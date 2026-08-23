# rcheevos Helper

`rom-metadata-rcheevos` is the native bridge between this framework and
rcheevos game-identification logic.

The helper is original code from this project. rcheevos itself remains an
upstream dependency and is not vendored into this repository.

## Supported commands

Version:

~~~text
rom-metadata-rcheevos --version
~~~

Generate a RetroAchievements identifier:

~~~text
rom-metadata-rcheevos hash --console-id <id> --json <path>
~~~

The JSON interface is defined in
`docs/RCHEEVOS_HELPER_CONTRACT.md`.

## Building locally

Obtain the rcheevos source separately and check out the revision recorded in
`../provenance.yaml`.

Then run:

~~~text
cd adapters/rcheevos/helper
./build-local /path/to/rcheevos/source /path/to/output
~~~

The resulting executable is:

~~~text
/path/to/output/rom-metadata-rcheevos
~~~

The build script compiles against the supplied rcheevos source tree. It does
not download dependencies and does not copy rcheevos source into this
repository.

## Compiler mode

The helper and pinned rcheevos sources are currently compiled using GNU C11.

This is necessary on Unix-like systems because rcheevos uses interfaces such
as `strdup`, `strcasecmp`, and `strncasecmp` whose declarations are exposed by
the platform in GNU/POSIX compilation modes.

Warnings are treated as errors.

## Licensing

The helper source is part of this project's MIT-licensed code.

rcheevos is separately licensed under MIT. Its upstream license text and
provenance information are retained in the parent adapter directory.

## Validation

Development validation includes:

- native helper version reporting;
- command-line error handling;
- missing-file handling;
- multiple real SNES revisions kept outside this repository;
- a local synthetic 512-byte-header case proving that rcheevos
  platform-specific hashing is distinct from generic whole-file MD5 hashing.

ROM files used for local validation are not part of this repository.
