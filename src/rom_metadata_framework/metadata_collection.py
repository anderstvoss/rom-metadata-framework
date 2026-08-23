from __future__ import annotations

from dataclasses import dataclass

from .canonical import CanonicalReleaseIdentity
from .contracts import MetadataProviderContractError
from .identification import IdentificationResult
from .local_metadata import LocalContentMetadata
from .metadata_provider import (
    MetadataProvider,
    MetadataProviderResult,
)
from .metadata_reconciliation import (
    MetadataReconciliationReport,
    reconcile_metadata,
)


@dataclass(frozen=True, slots=True)
class MetadataCollectionReport:
    """Observed results from one ordered metadata-provider pass."""

    attempted: tuple[str, ...]
    unmatched: tuple[str, ...]
    results: tuple[MetadataProviderResult, ...]

    def __post_init__(self) -> None:
        attempted = tuple(name.strip().lower() for name in self.attempted)
        unmatched = tuple(name.strip().lower() for name in self.unmatched)

        if any(not name for name in attempted):
            raise ValueError("attempted metadata provider names must not be empty")

        if any(not name for name in unmatched):
            raise ValueError("unmatched metadata provider names must not be empty")

        if len(set(attempted)) != len(attempted):
            raise ValueError("attempted metadata provider names must be unique")

        if len(set(unmatched)) != len(unmatched):
            raise ValueError("unmatched metadata provider names must be unique")

        attempted_set = set(attempted)
        unmatched_set = set(unmatched)

        if not unmatched_set <= attempted_set:
            raise ValueError("unmatched metadata providers must have been attempted")

        result_names = tuple(result.provider for result in self.results)

        if len(set(result_names)) != len(result_names):
            raise ValueError("metadata collection results must have unique providers")

        if not set(result_names) <= attempted_set:
            raise ValueError("matched metadata providers must have been attempted")

        expected_matched = tuple(
            name for name in attempted if name not in unmatched_set
        )

        if result_names != expected_matched:
            raise ValueError(
                "matched and unmatched providers must partition "
                "attempted providers in registration order"
            )

        object.__setattr__(self, "attempted", attempted)
        object.__setattr__(self, "unmatched", unmatched)

    @property
    def matched(self) -> tuple[str, ...]:
        """Provider names that returned matched records."""

        return tuple(result.provider for result in self.results)


@dataclass(frozen=True, slots=True)
class MetadataProviderCollection:
    """Ordered collection of independent metadata providers."""

    providers: tuple[MetadataProvider, ...]

    def __post_init__(self) -> None:
        names = tuple(provider.name.strip().lower() for provider in self.providers)

        if any(not name for name in names):
            raise ValueError("metadata provider names must not be empty")

        if len(set(names)) != len(names):
            raise ValueError("metadata provider names must be unique")

    def collect(
        self,
        identity: CanonicalReleaseIdentity,
    ) -> MetadataCollectionReport:
        """Collect independent provider observations in order."""

        attempted = []
        unmatched = []
        results = []

        for provider in self.providers:
            provider_name = provider.name.strip().lower()
            attempted.append(provider_name)

            result = provider.lookup_metadata(identity)

            if result is None:
                unmatched.append(provider_name)
                continue

            if result.provider != provider_name:
                raise MetadataProviderContractError(
                    (
                        "metadata provider result source does not match "
                        "the provider that returned it: "
                        f"{result.provider!r} != {provider_name!r}"
                    ),
                    component=provider_name,
                    operation="lookup_metadata",
                    field="provider",
                )

            results.append(result)

        return MetadataCollectionReport(
            attempted=tuple(attempted),
            unmatched=tuple(unmatched),
            results=tuple(results),
        )


@dataclass(frozen=True, slots=True)
class MetadataEnrichmentResult:
    """Identification evidence together with provider enrichment.

    Local metadata remains structurally separate from provider-supplied
    ReleaseMetadata. This object composes both evidence sources for
    consumers without assigning precedence between them.
    """

    identification: IdentificationResult
    provider_report: MetadataCollectionReport | None = None

    @property
    def canonical_identity(
        self,
    ) -> CanonicalReleaseIdentity | None:
        """Canonical release selected by identification reconciliation."""

        return self.identification.canonical_match

    @property
    def local_metadata(
        self,
    ) -> LocalContentMetadata | None:
        """Metadata extracted directly from represented content."""

        return self.identification.local_metadata

    @property
    def provider_results(
        self,
    ) -> tuple[MetadataProviderResult, ...]:
        """Matched provider observations, preserving provider order."""

        if self.provider_report is None:
            return ()

        return self.provider_report.results

    @property
    def metadata_collection_attempted(self) -> bool:
        """Whether provider metadata collection was performed."""

        return self.provider_report is not None

    @property
    def has_local_metadata(self) -> bool:
        """Whether local structural metadata is available."""

        return self.local_metadata is not None

    @property
    def has_provider_metadata(self) -> bool:
        """Whether any provider returned matched metadata."""

        return bool(self.provider_results)

    @property
    def has_metadata(self) -> bool:
        """Whether either local or provider metadata is available."""

        return self.has_local_metadata or self.has_provider_metadata

    @property
    def has_metadata_divergence(self) -> bool:
        """Whether comparable local and provider metadata diverges."""

        return self.metadata_reconciliation.has_divergence

    @property
    def metadata_reconciliation(
        self,
    ) -> MetadataReconciliationReport:
        """Compare compatible local and provider metadata evidence.

        Reconciliation is derived from the retained evidence layers and
        does not assign precedence, alter canonical identity, or affect
        verification or naming.
        """

        return reconcile_metadata(
            self.local_metadata,
            self.provider_results,
        )


def collect_identification_metadata(
    identification: IdentificationResult,
    providers: MetadataProviderCollection,
) -> MetadataEnrichmentResult:
    """Enrich an identified release without merging evidence layers.

    Provider metadata collection requires a canonical release identity.
    Locally extracted metadata remains available even when no canonical
    release was resolved and therefore no provider lookup can be made.
    """

    canonical = identification.canonical_match

    if canonical is None:
        return MetadataEnrichmentResult(
            identification=identification,
        )

    return MetadataEnrichmentResult(
        identification=identification,
        provider_report=providers.collect(canonical),
    )
