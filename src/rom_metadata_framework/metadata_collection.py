from __future__ import annotations

from dataclasses import dataclass

from .canonical import CanonicalReleaseIdentity
from .metadata_provider import (
    MetadataProvider,
    MetadataProviderResult,
)


@dataclass(frozen=True, slots=True)
class MetadataCollectionReport:
    """Observed results from one ordered metadata-provider pass."""

    attempted: tuple[str, ...]
    unmatched: tuple[str, ...]
    results: tuple[MetadataProviderResult, ...]

    def __post_init__(self) -> None:
        attempted = tuple(
            name.strip().lower()
            for name in self.attempted
        )
        unmatched = tuple(
            name.strip().lower()
            for name in self.unmatched
        )

        if any(not name for name in attempted):
            raise ValueError(
                "attempted metadata provider names must not be empty"
            )

        if any(not name for name in unmatched):
            raise ValueError(
                "unmatched metadata provider names must not be empty"
            )

        if len(set(attempted)) != len(attempted):
            raise ValueError(
                "attempted metadata provider names must be unique"
            )

        if len(set(unmatched)) != len(unmatched):
            raise ValueError(
                "unmatched metadata provider names must be unique"
            )

        attempted_set = set(attempted)
        unmatched_set = set(unmatched)

        if not unmatched_set <= attempted_set:
            raise ValueError(
                "unmatched metadata providers must have been attempted"
            )

        result_names = tuple(
            result.provider
            for result in self.results
        )

        if len(set(result_names)) != len(result_names):
            raise ValueError(
                "metadata collection results must have unique providers"
            )

        if not set(result_names) <= attempted_set:
            raise ValueError(
                "matched metadata providers must have been attempted"
            )

        expected_matched = tuple(
            name
            for name in attempted
            if name not in unmatched_set
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

        return tuple(
            result.provider
            for result in self.results
        )



@dataclass(frozen=True, slots=True)
class MetadataProviderCollection:
    """Ordered collection of independent metadata providers."""

    providers: tuple[MetadataProvider, ...]

    def __post_init__(self) -> None:
        names = tuple(
            provider.name.strip().lower()
            for provider in self.providers
        )

        if any(not name for name in names):
            raise ValueError(
                "metadata provider names must not be empty"
            )

        if len(set(names)) != len(names):
            raise ValueError(
                "metadata provider names must be unique"
            )

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
                raise ValueError(
                    "metadata provider result source does not match "
                    "the provider that returned it: "
                    f"{result.provider!r} != {provider_name!r}"
                )

            results.append(result)

        return MetadataCollectionReport(
            attempted=tuple(attempted),
            unmatched=tuple(unmatched),
            results=tuple(results),
        )
