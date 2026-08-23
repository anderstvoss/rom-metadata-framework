# Third-Party Provenance Policy

## Purpose

This project may depend on emulators, disc-image utilities, metadata tools,
libraries, and other open-source projects.

All material third-party dependencies must remain traceable to their upstream
source and license.

## Integration classes

A third-party dependency may be integrated as:

~~~text
external-process
linked-library
embedded-source
translated-source
reimplemented-from-specification
other
~~~

The preferred order is:

1. original implementation from public specifications;
2. permissively licensed library;
3. independently installed external executable;
4. third-party-derived source only when necessary.

## External-tool adapters

An adapter that invokes an independently installed executable must include:

~~~text
UPSTREAM.md
provenance.yaml
~~~

`LICENSE.upstream` is optional when the upstream license is not redistributed
with this repository, but `UPSTREAM.md` and `provenance.yaml` must identify the
license and canonical upstream source.

The adapter must document:

- executable name;
- upstream project;
- upstream repository;
- upstream license;
- supported versions;
- command or interface used;
- whether the dependency is optional or required;
- whether this repository redistributes any upstream binary or source.

External-process integration does not remove attribution requirements.

## Source-derived adapters

Any adapter containing code copied, translated, adapted, or substantially
derived from another project must include:

~~~text
UPSTREAM.md
LICENSE.upstream
provenance.yaml
~~~

`LICENSE.upstream` must contain the applicable upstream license text.

`UPSTREAM.md` must document:

- upstream project;
- upstream repository;
- exact upstream revision where practical;
- upstream license;
- functionality reused;
- upstream files or functions involved;
- local implementation approach;
- material modifications;
- required attribution.

## provenance.yaml

Each adapter with a material external dependency must contain a machine-readable
provenance record.

Minimum structure:

~~~yaml
upstream:
  project: ""
  repository: ""
  revision: ""
  license: ""
  supported_versions: ""

integration:
  method: ""
  dependency: ""
  redistributed: false
  required: false
  description: ""

derived_files: []

modifications: []

review:
  last_reviewed: ""
~~~

For an external executable, `revision` may identify a tested version, release,
or compatible version range rather than a source commit.

For source-derived code, `revision` should identify a specific upstream source
revision whenever practical.

## Original reimplementation

An implementation based on public specifications should identify those
specification sources.

Do not describe code as an original reimplementation if another project's
source code materially informed its implementation.

## External dependency credit

Projects that materially provide parsing, hashing, conversion, identification,
or metadata functionality should be credited in user-facing documentation.

Formal notices must also be preserved whenever required by the upstream
license.

## Test fixtures

Third-party test fixtures must have documented provenance and redistribution
permission.

Commercial ROMs, disc images, executables, firmware, encryption keys, private
keys, or extracted copyrighted game assets must not be committed.

## Review requirement

No material third-party dependency may be merged until:

1. its upstream project has been identified;
2. its license has been identified;
3. the integration method has been documented;
4. redistribution status has been documented;
5. required attribution exists;
6. test data is safe to distribute;
7. repository sanitation checks pass.
