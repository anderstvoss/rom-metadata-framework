from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .canonical import CanonicalReleaseIdentity
from .content import NormalizedContentIdentity
from .detection import PlatformDetection, PlatformDetector
from .hashing import GenericHashAdapter
from .identity import RomIdentity
from .local_metadata import LocalContentMetadata
from .lookup import LookupIdentity
from .reconciliation import (
    PlatformReconciliation,
    reconcile_platform,
)
from .release_reconciliation import (
    ReleaseReconciliation,
    reconcile_release_matches,
)
from .routing import NoSupportingNormalizerError
from .verification import (
    DEFAULT_VERIFICATION_POLICY,
    VerificationPolicy,
    VerificationReport,
    VerificationStatus,
    verify_release,
)


class LookupResolver(Protocol):
    """Provider capable of resolving explicit lookup identities."""

    def identify(
        self,
        identity: RomIdentity,
    ) -> CanonicalReleaseIdentity | None:
        """Identify from physical-file identity."""
        ...

    def identify_lookup(
        self,
        lookup: LookupIdentity,
    ) -> CanonicalReleaseIdentity | None:
        """Identify from an explicit lookup identity."""
        ...


class NormalizedContentResult(Protocol):
    """Result exposing normalized content identity."""

    @property
    def content(self) -> NormalizedContentIdentity:
        """Normalized content represented by the source file."""
        ...


class ContentNormalizer(Protocol):
    """Adapter capable of producing normalized content."""

    def identify(
        self,
        path: Path,
    ) -> NormalizedContentResult:
        """Return normalized content represented by one file."""
        ...


@dataclass(frozen=True, slots=True)
class IdentificationResult:
    """Complete identification evidence for one physical file."""

    physical_identity: RomIdentity
    platform_detection: PlatformDetection

    physical_match: CanonicalReleaseIdentity | None = None
    normalized_content: NormalizedContentIdentity | None = None
    local_metadata: LocalContentMetadata | None = None
    normalized_match: CanonicalReleaseIdentity | None = None

    release_reconciliation: ReleaseReconciliation | None = None
    platform_reconciliation: PlatformReconciliation | None = None

    @property
    def canonical_match(self) -> CanonicalReleaseIdentity | None:
        """Return the strongest available canonical release match."""

        reconciliation = self.release_reconciliation

        if reconciliation is None:
            reconciliation = reconcile_release_matches(
                self.physical_match,
                self.normalized_match,
            )

        return reconciliation.selected

    @property
    def matched_via_normalization(self) -> bool:
        """Whether identification required normalized content."""

        return self.physical_match is None and self.normalized_match is not None

    @property
    def physical_representation_matched(self) -> bool:
        """Whether the exact physical representation matched a provider."""

        return self.physical_match is not None

    @property
    def normalized_content_matched(self) -> bool:
        """Whether normalized content matched a provider."""

        return self.normalized_match is not None


def identify_file(
    path: Path,
    *,
    detector: PlatformDetector,
    resolver: LookupResolver,
    normalizer: ContentNormalizer | None = None,
) -> IdentificationResult:
    """Identify one file while preserving physical and normalized evidence."""

    path = Path(path)

    physical_identity = GenericHashAdapter().identify(path)
    platform_detection = detector.detect(path)

    physical_match = resolver.identify(physical_identity)

    normalized_content = None
    local_metadata = None
    normalized_match = None

    if normalizer is not None:
        try:
            normalized_result = normalizer.identify(path)
        except NoSupportingNormalizerError:
            normalized_result = None

        if normalized_result is not None:
            normalized_content = normalized_result.content

            candidate_local_metadata = getattr(
                normalized_result,
                "local_metadata",
                None,
            )

            if candidate_local_metadata is not None and not isinstance(
                candidate_local_metadata,
                LocalContentMetadata,
            ):
                raise TypeError(
                    "normalizer local_metadata must be LocalContentMetadata or None"
                )

            local_metadata = candidate_local_metadata

            lookup = LookupIdentity(
                file_name=physical_identity.file_name or path.name,
                file_size=physical_identity.file_size
                if physical_identity.file_size is not None
                else path.stat().st_size,
                hashes=normalized_content.hashes,
            )

            normalized_match = resolver.identify_lookup(lookup)

    release_reconciliation = reconcile_release_matches(
        physical_match,
        normalized_match,
    )

    provider_platform = None

    if (
        physical_match is not None
        and normalized_match is not None
        and physical_match.platform == normalized_match.platform
    ):
        provider_platform = physical_match.platform
    elif release_reconciliation.selected is not None:
        provider_platform = release_reconciliation.selected.platform

    reconciliation = reconcile_platform(
        platform_detection,
        provider_platform=provider_platform,
    )

    return IdentificationResult(
        physical_identity=physical_identity,
        platform_detection=platform_detection,
        physical_match=physical_match,
        normalized_content=normalized_content,
        local_metadata=local_metadata,
        normalized_match=normalized_match,
        release_reconciliation=release_reconciliation,
        platform_reconciliation=reconciliation,
    )


@dataclass(frozen=True, slots=True)
class IdentificationVerification:
    """Verification of physical representation and normalized content."""

    physical: VerificationReport | None = None
    normalized: VerificationReport | None = None
    release_reconciliation: ReleaseReconciliation | None = None

    @property
    def physical_known_good(self) -> bool:
        return bool(self.physical is not None and self.physical.known_good)

    @property
    def normalized_known_good(self) -> bool:
        return bool(self.normalized is not None and self.normalized.known_good)

    @property
    def content_known_good(self) -> bool:
        """Whether either exact physical or normalized content is known good."""

        return self.physical_known_good or self.normalized_known_good

    @property
    def representation_known_good(self) -> bool:
        """Whether the exact physical representation is known good."""

        return self.physical_known_good

    @property
    def has_known_bad(self) -> bool:
        """Whether either verification path identifies known-bad content."""

        return any(
            report is not None and report.status is VerificationStatus.KNOWN_BAD
            for report in (
                self.physical,
                self.normalized,
            )
        )

    @property
    def has_conflicts(self) -> bool:
        """Whether verification or release reconciliation conflicts exist."""

        verification_conflict = any(
            report is not None and report.status is VerificationStatus.CONFLICT
            for report in (
                self.physical,
                self.normalized,
            )
        )

        release_conflict = bool(
            self.release_reconciliation is not None
            and self.release_reconciliation.has_conflict
        )

        return verification_conflict or release_conflict

    @property
    def safe_for_canonical_naming(self) -> bool:
        """Whether verified content may safely supply a canonical name."""

        return (
            self.content_known_good
            and not self.has_known_bad
            and not self.has_conflicts
        )


def verify_identification(
    result: IdentificationResult,
    *,
    policy: VerificationPolicy = DEFAULT_VERIFICATION_POLICY,
) -> IdentificationVerification:
    """Verify physical and normalized matches independently."""

    effective_policy = policy

    physical_report = (
        verify_release(
            result.physical_match,
            policy=effective_policy,
        )
        if result.physical_match is not None
        else None
    )

    normalized_report = (
        verify_release(
            result.normalized_match,
            policy=effective_policy,
        )
        if result.normalized_match is not None
        else None
    )

    return IdentificationVerification(
        physical=physical_report,
        normalized=normalized_report,
        release_reconciliation=result.release_reconciliation,
    )
