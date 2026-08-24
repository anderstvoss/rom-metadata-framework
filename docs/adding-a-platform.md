# Adding a Platform

This guide describes how to extend the standard ROM Metadata Framework runtime
without collapsing physical identity, structural metadata, canonical content,
provider lookup, or release identity into one platform-specific parser.

## Start with the evidence model

Before writing code, determine which forms of evidence the platform can
actually produce.

A platform integration may need one or more of:

1. a platform detector;
2. a structural inspector;
3. a canonical-content normalizer;
4. a specialist integrity verifier;
5. a provider/platform mapping.

These are separate responsibilities.

Do not add a normalizer merely because a detector or structural parser exists.

## Detector

A detector answers:

> What platform does this physical artifact appear to belong to?

It returns platform candidates with confidence and provenance-bearing evidence.

Detector rules:

- prefer format-native signatures or structures over filenames/extensions;
- use bounded or random-access reads for large images;
- do not scan multi-gigabyte files sequentially only to determine platform;
- do not perform provider lookup;
- do not create canonical release identity;
- avoid filesystem-only assumptions when multiple generations share the same
  filesystem or container format.

When practical, malformed or unrelated input should be treated as unsupported
rather than causing an operational failure.

## Structural inspector

A structural inspector extracts trustworthy facts directly from the represented
artifact without creating normalized content.

It may return:

- `RepresentationIdentity`;
- `LocalContentMetadata`;
- or both.

Typical structural evidence includes:

- physical/container format;
- filesystem type;
- product or title identifiers;
- boot path;
- executable version;
- disc number;
- region/language data;
- internal titles;
- other artifact-local metadata.

Structural inspection must not:

- initiate normalized provider lookup;
- claim canonical-content hashes unless it actually constructs or identifies
  canonical content;
- turn provider metadata into local metadata.

For large images, inspection must remain bounded/random-access.

## Normalizer

A normalizer is appropriate only when the platform has a meaningful transform
from the physical representation to a canonical or normalized content identity.

Examples include:

- removing representation-specific headers;
- reconstructing a canonical disc-image representation;
- deriving a canonical filesystem/content identity through a defined transform.

A normalizer is not required for every platform.

If structural inspection already extracts useful identifiers but no defensible
canonical byte/content transform exists, implement detection and inspection
without adding a normalizer.

Normalized hashes belong to `NormalizedContentIdentity`. They must never replace
the whole-file hashes in `RomIdentity`.

## Specialist integrity verifier

A specialist integrity verifier evaluates platform-specific properties of the
physical artifact that are not equivalent to provider/catalogue identification.

Examples may include:

- optical-disc sector/layout validation;
- IRD-based validation;
- cryptographic signature verification;
- platform-specific authenticated-container checks.

Integrity verification must remain separate from `verify_release()`, which
evaluates catalogue-backed release evidence.

An integrity verifier must not manufacture canonical release identity or
normalized-content hashes. Its result is an independent physical-artifact trust
observation.

The default runtime currently contains no specialist integrity verifier.

## External backends

An external executable may be preferable when:

- the tool already implements a complex canonical reconstruction;
- directly incorporating upstream source would create licensing or provenance
  coupling;
- the external boundary is easier to validate and maintain.

External integrations must follow:

- [Runtime Backends](runtime-backends.md);
- [Licensing Policy](LICENSING.md);
- [Third-Party Provenance Policy](THIRD_PARTY_PROVENANCE.md).

Document executable discovery, supported operations, failure behavior, and
temporary-storage requirements.

## Provider mappings

Provider/platform registration is independent from detector, inspector, and
normalizer support.

A RetroAchievements/rcheevos mapping or another provider mapping does not mean
the standard runtime can structurally recognize the platform.

Likewise, a platform may have useful built-in structural support without a
provider mapping.

Do not infer implementation support from provider registration alone.

## Standard-runtime registration

When adding a standard component:

1. register the detector, inspector, or normalizer in the relevant builder in
   `defaults.py`;
2. update the component-to-platform ownership maps in `support.py`;
3. add or update the corresponding `PlatformSupport` entry;
4. run `default_support_drift()` and keep the result empty.

The support inventory is the source used by:

~~~text
rom-metadata platforms
~~~

and should agree with the actual default runtime.

## Testing

Public tests must use synthetic, original, or freely redistributable fixtures.

Tests should cover, as relevant:

- a positive detector case;
- malformed/truncated input;
- unrelated input;
- bounded/random-access behavior;
- structural metadata fields;
- representation identity;
- inspector/normalizer evidence agreement;
- conflicting evidence;
- provider/platform reconciliation;
- normalization output;
- backend absence/failure for external integrations;
- support-inventory drift.

Do not commit private ROM names, private filesystem paths, commercial ROM or
disc content, extracted proprietary executables, credentials, or private
validation-corpus identifiers.

Private local validation may be used before publication, but all tracked tests
must remain publicly redistributable.

## Documentation

A platform implementation should update, as applicable:

- the support matrix in `README.md`;
- platform-specific architecture notes in `ARCHITECTURE.md`;
- runtime backend documentation;
- third-party provenance documentation;
- changelog/release notes.

Document important limitations explicitly. Examples include encrypted
representations that cannot be inspected, missing canonical normalization
paths, or provider mappings that are not currently available.

## Pull-request checklist

Before opening a platform pull request, verify:

- [ ] canonical platform name and aliases are deliberate;
- [ ] detector behavior is content/structure based;
- [ ] large-file detection and inspection are bounded/random-access;
- [ ] inspector and normalizer responsibilities are separated;
- [ ] specialist integrity verification is separate from catalogue-backed release verification;
- [ ] physical hashes remain physical-file hashes;
- [ ] normalized hashes exist only when canonical content exists;
- [ ] local metadata remains separate from provider metadata;
- [ ] provider lookup ordering is unchanged unless intentionally documented;
- [ ] provider mappings do not masquerade as implementation support;
- [ ] support inventory and default runtime do not drift;
- [ ] public fixtures are redistributable;
- [ ] third-party licensing/provenance has been reviewed;
- [ ] the full test and coverage gates pass;
- [ ] Ruff passes;
- [ ] package-artifact checks pass when packaging is affected;
- [ ] `./scripts/pre-public-check` passes.
