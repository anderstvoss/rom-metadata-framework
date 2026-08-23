# Metadata Selection Policy

## Current contract

ROM Metadata Framework does not define a framework-wide preferred-value policy
for release metadata.

Provider metadata is retained as provenance-bearing evidence. Multiple providers
may supply different values for the same field, and those values remain
independently represented.

The framework currently follows these rules:

1. provider registration order is operational ordering only;
2. provider order is not metadata precedence;
3. `MetadataProvenance.authoritative` does not establish cross-provider ranking;
4. local metadata and provider metadata remain structurally separate;
5. metadata reconciliation is diagnostic only;
6. reconciliation does not select, replace, suppress, or rank values;
7. metadata enrichment does not alter canonical release identity;
8. metadata enrichment does not alter verification;
9. metadata enrichment does not alter naming;
10. consumers that need one display, export, or storage value must define an
    explicit policy for that use case.

## Provider order

`MetadataProviderCollection` calls providers in registration order and preserves
that order in its report.

This ordering exists to make execution and reporting deterministic. It must not
be interpreted as:

- first provider wins;
- earlier providers are more trusted;
- later providers are fallbacks;
- provider position is a ranking signal.

All matched provider results remain available to consumers.

## Authoritative provenance

`MetadataProvenance.authoritative` is provenance attached to an individual
provider-supplied value.

The framework does not currently define semantics that compare this flag across
providers or use it to choose a preferred value.

In particular, `authoritative=True` does not:

- suppress non-authoritative values;
- cause a provider to outrank another provider;
- make one title, region, developer, publisher, or other field canonical;
- alter canonical release identity;
- affect verification;
- affect naming.

Future consumers may choose to use provenance authority as one input to an
explicit selection policy, but such policy must define its own scope and
conflict behavior.

## Reconciliation

Metadata reconciliation compares compatible local and provider fields.

Current comparable fields are:

- titles;
- developers;
- publishers;
- regions;
- languages;
- player counts;
- multiplayer features.

Reconciliation reports relationships such as agreement, partial agreement, and
divergence. It does not produce a preferred metadata value.

Provider values are aggregated across matched providers before comparison.
Provider identity and ordering are not used as precedence signals.

Fields without a sufficiently defined common semantic representation remain
outside reconciliation until explicit mappings exist.

## Separation from canonical identity

Metadata enrichment begins only after canonical release identity has been
resolved.

Provider metadata lookup receives the already reconciled canonical identity.
Provider metadata therefore cannot participate in selecting that identity.

Local metadata likewise remains corroborating or descriptive evidence and does
not alter provider lookup ordering or canonical identity.

## Separation from verification and naming

Verification is derived from canonical release and catalogue evidence.

Naming is derived from canonical release identity together with identification
verification.

Neither workflow consumes enriched release metadata or metadata reconciliation.
Consequently, disagreement between metadata providers cannot by itself rename a
file, establish trust, revoke trust, or change canonical release identity.

## Consumer-specific selection

Some consumers will eventually need a single value, for example:

- one display title;
- one release date for a regional UI;
- one cover image;
- one developer string for export;
- one preferred language.

Those choices are context-dependent and should not be inferred from collection
order.

A future selection API should be introduced only when a concrete consumer
defines requirements such as:

- field being selected;
- target region or language;
- acceptable providers;
- authority semantics;
- conflict handling;
- fallback behavior;
- preservation of the underlying evidence.

Until such a requirement exists, the framework intentionally exposes evidence
and reconciliation rather than a default winner.

## Non-goals

The current framework does not implement:

- first-provider-wins selection;
- last-provider-wins selection;
- global authority-first ranking;
- provider priority weights;
- automatic field-specific winners;
- metadata-derived canonical identity;
- metadata-derived naming or verification decisions.

This absence is intentional rather than an unfinished default-selection
algorithm.
