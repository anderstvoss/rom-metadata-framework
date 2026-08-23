# rcheevos Helper Contract

## Purpose

`rom-metadata-rcheevos` is a small native helper that isolates the rcheevos C
API from the Python framework.

The helper performs platform-aware RetroAchievements hashing. It does not
replace generic CRC32, MD5, or SHA-1 hashing.

## Version command

~~~text
rom-metadata-rcheevos --version
~~~

Successful output:

~~~text
rom-metadata-rcheevos <helper-version> rcheevos <rcheevos-version>
~~~

## Hash command

Initial interface:

~~~text
rom-metadata-rcheevos hash --console-id <id> --json <path>
~~~

For SNES:

~~~text
rom-metadata-rcheevos hash --console-id 3 --json <path>
~~~

## Successful JSON result

~~~json
{
  "schema_version": 1,
  "console_id": 3,
  "hash": "cdd3c8c37322978ca8669b34bc89c804",
  "backend": "rcheevos",
  "backend_version": "12.4.0"
}
~~~

The `hash` field is a RetroAchievements platform-aware identifier. It must be
stored as:

~~~text
specialized_identifiers["retroachievements"]
~~~

It must not be written to `HashSet.md5`, even when the resulting value happens
to equal the generic whole-file MD5.

## Standard output

When `--json` is used, stdout contains exactly one JSON document.

Diagnostics must be written to stderr so they cannot corrupt machine-readable
stdout.

## Exit status

- `0`: hash generated successfully
- `2`: invalid command-line arguments
- `3`: input file could not be opened or read
- `4`: rcheevos could not generate an identifier for the requested console
- `5`: internal/helper failure

Additional statuses may be added only with corresponding documentation and
tests.

## Path handling

The helper receives the ROM path as a discrete process argument.

The Python caller must not:

- invoke a shell;
- interpolate the path into command text;
- interpret shell metacharacters contained in filenames.

The existing backend runtime provides this boundary.

## Hashing responsibility

Console-specific hashing behavior belongs to rcheevos.

The Python framework must not pre-strip headers, transform images, or otherwise
modify content before invoking this helper unless a future integration
explicitly documents such a requirement.

For SNES, this means copier-header handling is performed by rcheevos rather
than duplicated in Python.

## Local validation

The initial local validation suite contains multiple independent SNES titles,
multiple official revisions, and a synthetic copy of one ROM with a 512-byte
prefix.

The synthetic pair is expected to demonstrate:

1. different generic whole-file hashes;
2. identical RetroAchievements specialized identifiers.

Local ROM paths and ROM contents must never be committed.
