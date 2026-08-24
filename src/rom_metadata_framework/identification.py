from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from .canonical import CanonicalReleaseIdentity
from .content import NormalizedContentIdentity
from .contracts import (
    InspectionContractError,
    NormalizerContractError,
    StructuralEvidenceConflictError,
)
from .detection import PlatformDetection, PlatformDetector
from .hashing import GenericHashAdapter
from .identity import RomIdentity
from .inspection import (
    StructuralInspectionResult,
    StructuralInspector,
)
from .local_metadata import LocalContentMetadata
from .lookup import LookupIdentity
from .normalization import NormalizationResult
from .reconciliation import (
    PlatformReconciliation,
    reconcile_platform,
)
from .release_reconciliation import (
    ReleaseReconciliation,
    reconcile_release_matches,
)
from .representation import RepresentationIdentity
from .resolvers import ResolverUnavailableError
from .routing import NoSupportingNormalizerError
from .selection import (
    IdentificationSelection,
    identifiers_equal,
    local_primary_identifier,
)
from .verification import (
    DEFAULT_VERIFICATION_POLICY,
    VerificationPolicy,
    VerificationReport,
    VerificationStatus,
    verify_release,
)


class RequestedPlatformUnresolvedError(RuntimeError):
    """Raised when a hard platform restriction does not match locally."""

    def __init__(
        self,
        *,
        platform: str,
    ) -> None:
        self.platform = platform

        super().__init__(
            "unable to establish restricted platform "
            f"{platform} from local evidence"
        )


class RequestedIdentityError(RuntimeError):
    """Base failure while testing a restricted requested identity."""


class RequestedIdentityMismatchError(
    RequestedIdentityError
):
    """Raised when local evidence contradicts a restricted identity."""

    def __init__(
        self,
        *,
        platform: str,
        requested_identifier: str,
        observed_identifier: str,
    ) -> None:
        self.platform = platform
        self.requested_identifier = requested_identifier
        self.observed_identifier = observed_identifier

        super().__init__(
            "requested identity "
            f"{platform}:{requested_identifier} "
            "does not match local structural identity "
            f"{platform}:{observed_identifier}"
        )


class RequestedIdentityUnresolvedError(
    RequestedIdentityError
):
    """Raised when restricted identity cannot be established locally."""

    def __init__(
        self,
        *,
        platform: str,
        requested_identifier: str,
    ) -> None:
        self.platform = platform
        self.requested_identifier = requested_identifier

        super().__init__(
            "unable to establish restricted identity "
            f"{platform}:{requested_identifier} "
            "from local structural evidence"
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


class ContentNormalizer(Protocol):
    """Adapter capable of producing normalized content evidence."""

    def identify(
        self,
        path: Path,
    ) -> NormalizationResult:
        """Return complete normalization evidence for one file."""
        ...



class ProviderLookupStatus(StrEnum):
    """Outcome of one release-provider lookup attempt."""

    NOT_ATTEMPTED = "not_attempted"
    MATCHED = "matched"
    NO_MATCH = "no_match"
    UNAVAILABLE = "unavailable"



class IdentificationStrength(StrEnum):
    """Overall strength of the resolved identification evidence."""

    CATALOGUE = "catalogue"
    LOCAL_STRONG = "local_strong"
    LOCAL_PROBABLE = "local_probable"
    UNRESOLVED = "unresolved"


class IdentificationTitleSource(StrEnum):
    """Source of the best human-readable title."""

    CATALOGUE = "catalogue"
    EMBEDDED = "embedded"
    UNAVAILABLE = "unavailable"



class RequestedIdentityStatus(StrEnum):
    """Relationship between a requested identity and observed local evidence."""

    MATCHED = "matched"
    MISMATCH = "mismatch"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class RequestedIdentityAssessment:
    """Assessment of one user-supplied platform-native identity."""

    platform: str
    requested_identifier: str
    status: RequestedIdentityStatus
    observed_platform: str | None = None
    observed_identifier: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderLookupOutcome:
    """Provider availability and match state for one lookup path."""

    status: ProviderLookupStatus = (
        ProviderLookupStatus.NOT_ATTEMPTED
    )
    reason: str | None = None

    @property
    def attempted(self) -> bool:
        """Whether this provider lookup was attempted."""

        return (
            self.status
            is not ProviderLookupStatus.NOT_ATTEMPTED
        )

    @property
    def available(self) -> bool:
        """Whether an attempted lookup reached the provider."""

        return self.status in {
            ProviderLookupStatus.MATCHED,
            ProviderLookupStatus.NO_MATCH,
        }



def _assess_requested_identity(
    *,
    selection: IdentificationSelection | None,
    platform_detection: PlatformDetection,
    local_metadata: LocalContentMetadata | None,
) -> RequestedIdentityAssessment | None:
    """Compare a soft requested identity with observed local evidence."""

    if (
        selection is None
        or selection.identity is None
    ):
        return None

    requested = selection.identity
    best = platform_detection.best

    if (
        best is not None
        and best.platform != requested.platform
    ):
        observed_identifier = None

        if local_metadata is not None:
            observed_identifier = local_primary_identifier(
                local_metadata,
                platform=best.platform,
            )

        return RequestedIdentityAssessment(
            platform=requested.platform,
            requested_identifier=requested.identifier,
            status=RequestedIdentityStatus.MISMATCH,
            observed_platform=best.platform,
            observed_identifier=observed_identifier,
        )

    observed_identifier = local_primary_identifier(
        local_metadata,
        platform=requested.platform,
    )

    if observed_identifier is None:
        return RequestedIdentityAssessment(
            platform=requested.platform,
            requested_identifier=requested.identifier,
            status=RequestedIdentityStatus.UNRESOLVED,
            observed_platform=(
                best.platform
                if best is not None
                else None
            ),
        )

    return RequestedIdentityAssessment(
        platform=requested.platform,
        requested_identifier=requested.identifier,
        status=(
            RequestedIdentityStatus.MATCHED
            if identifiers_equal(
                observed_identifier,
                requested.identifier,
            )
            else RequestedIdentityStatus.MISMATCH
        ),
        observed_platform=requested.platform,
        observed_identifier=observed_identifier,
    )



def _merge_structural_evidence(
    current,
    incoming,
    *,
    field: str,
):
    if current is None:
        return incoming

    if incoming is None:
        return current

    if current != incoming:
        raise StructuralEvidenceConflictError(
            (
                "structural inspector and normalizer "
                f"{field} evidence disagree"
            ),
            field=field,
        )

    return current


@dataclass(frozen=True, slots=True)
class IdentificationResult:
    """Complete identification evidence for one physical file."""

    physical_identity: RomIdentity
    platform_detection: PlatformDetection

    physical_match: CanonicalReleaseIdentity | None = None
    normalized_content: NormalizedContentIdentity | None = None
    physical_representation: RepresentationIdentity | None = None
    local_metadata: LocalContentMetadata | None = None
    normalized_match: CanonicalReleaseIdentity | None = None

    release_reconciliation: ReleaseReconciliation | None = None
    platform_reconciliation: PlatformReconciliation | None = None

    physical_lookup: ProviderLookupOutcome = (
        ProviderLookupOutcome()
    )
    normalized_lookup: ProviderLookupOutcome = (
        ProviderLookupOutcome()
    )
    provider_name: str | None = None
    requested_identity: RequestedIdentityAssessment | None = None

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
    def identified(self) -> bool:
        """Whether reconciliation selected a canonical release."""

        return self.canonical_match is not None

    @property
    def has_normalized_content(self) -> bool:
        """Whether canonical-content normalization produced evidence."""

        return self.normalized_content is not None

    @property
    def has_physical_representation(self) -> bool:
        """Whether representation-specific evidence is available."""

        return self.physical_representation is not None

    @property
    def has_local_metadata(self) -> bool:
        """Whether metadata was extracted directly from represented content."""

        return self.local_metadata is not None

    @property
    def has_release_conflict(self) -> bool:
        """Whether physical and normalized release evidence conflicts."""

        return bool(
            self.release_reconciliation is not None
            and self.release_reconciliation.has_conflict
        )

    @property
    def has_platform_conflict(self) -> bool:
        """Whether local and provider platform evidence conflicts."""

        return bool(
            self.platform_reconciliation is not None
            and self.platform_reconciliation.has_conflict
        )

    @property
    def physical_representation_matched(self) -> bool:
        """Whether the exact physical representation matched a provider."""

        return self.physical_match is not None

    @property
    def normalized_content_matched(self) -> bool:
        """Whether normalized content matched a provider."""

        return self.normalized_match is not None


    @property
    def provider_unavailable(self) -> bool:
        """Whether any attempted provider lookup was unavailable."""

        return any(
            outcome.status
            is ProviderLookupStatus.UNAVAILABLE
            for outcome in (
                self.physical_lookup,
                self.normalized_lookup,
            )
        )

    @property
    def identification_strength(
        self,
    ) -> IdentificationStrength:
        """Return the strongest supported identification class."""

        if self.canonical_match is not None:
            return IdentificationStrength.CATALOGUE

        metadata = self.local_metadata
        detected_platform = (
            self.platform_detection.best is not None
        )

        if (
            metadata is not None
            and metadata.identifiers
            and detected_platform
        ):
            return IdentificationStrength.LOCAL_STRONG

        if detected_platform:
            return IdentificationStrength.LOCAL_PROBABLE

        if (
            metadata is not None
            and not metadata.empty
        ):
            return IdentificationStrength.LOCAL_PROBABLE

        return IdentificationStrength.UNRESOLVED

    @property
    def title_source(
        self,
    ) -> IdentificationTitleSource:
        """Return the provenance class of the best display title."""

        if self.canonical_match is not None:
            return IdentificationTitleSource.CATALOGUE

        if (
            self.local_metadata is not None
            and self.local_metadata.titles
        ):
            return IdentificationTitleSource.EMBEDDED

        return IdentificationTitleSource.UNAVAILABLE

    @property
    def display_title(self) -> str | None:
        """Return catalogue title first, then embedded local title."""

        canonical = self.canonical_match

        if canonical is not None:
            return canonical.title or canonical.release_name

        metadata = self.local_metadata

        if metadata is not None and metadata.titles:
            return metadata.titles[0].value

        return None



def _local_platforms(
    platform_detection: PlatformDetection,
    local_metadata: LocalContentMetadata | None,
) -> frozenset[str]:
    """Return locally asserted canonical platform names."""

    platforms: set[str] = set()

    if platform_detection.best is not None:
        platforms.add(
            platform_detection.best.platform
        )

    if (
        local_metadata is not None
        and local_metadata.platform is not None
    ):
        platforms.add(
            local_metadata.platform
        )

    return frozenset(platforms)


def _should_normalize(
    *,
    normalizer: ContentNormalizer | None,
    force_normalization: bool,
    physical_match: CanonicalReleaseIdentity | None,
    physical_lookup: ProviderLookupOutcome,
    platform_detection: PlatformDetection,
    local_metadata: LocalContentMetadata | None,
) -> bool:
    """Return whether normalized-content work adds useful evidence."""

    if normalizer is None:
        return False

    if force_normalization:
        return True

    if (
        physical_lookup.status
        is ProviderLookupStatus.UNAVAILABLE
    ):
        return False

    if (
        physical_match is None
        or not physical_match.has_authoritative_content_match
    ):
        return True

    local_platforms = _local_platforms(
        platform_detection,
        local_metadata,
    )

    if not local_platforms:
        return False

    return any(
        platform != physical_match.platform
        for platform in local_platforms
    )



def identify_file(
    path: Path,
    *,
    detector: PlatformDetector,
    resolver: LookupResolver,
    normalizer: ContentNormalizer | None = None,
    inspector: StructuralInspector | None = None,
    force_normalization: bool = False,
    selection: IdentificationSelection | None = None,
) -> IdentificationResult:
    """Identify one file while preserving independent evidence paths.

    Physical provider lookup occurs before optional structural inspection and
    content normalization. Structural inspection may add representation and
    local metadata evidence but never performs normalized provider lookup.
    """

    path = Path(path)

    platform_detection = None
    inspection_result = None

    restricted_selection = (
        selection is not None
        and selection.restrict
    )

    # Hard restrictions exist to avoid unrelated work. Establish the
    # requested platform using bounded local detection before hashing or
    # provider lookup. A restricted identity additionally requires the
    # platform-native identifier to agree before expensive work begins.
    if restricted_selection:
        assert selection is not None
        assert selection.effective_platform is not None

        requested_platform = (
            selection.effective_platform
        )

        platform_detection = detector.detect(
            path
        )

        best = platform_detection.best

        if (
            best is None
            or best.platform
            != requested_platform
        ):
            if selection.identity is not None:
                raise RequestedIdentityUnresolvedError(
                    platform=requested_platform,
                    requested_identifier=(
                        selection.identity.identifier
                    ),
                )

            raise RequestedPlatformUnresolvedError(
                platform=requested_platform,
            )

        if selection.identity is not None:
            if inspector is None:
                raise RequestedIdentityUnresolvedError(
                    platform=requested_platform,
                    requested_identifier=(
                        selection.identity.identifier
                    ),
                )

            inspection_result = inspector.inspect(
                path
            )

            if inspection_result is None:
                raise RequestedIdentityUnresolvedError(
                    platform=requested_platform,
                    requested_identifier=(
                        selection.identity.identifier
                    ),
                )

            observed_identifier = (
                local_primary_identifier(
                    inspection_result.local_metadata,
                    platform=requested_platform,
                )
            )

            if observed_identifier is None:
                raise RequestedIdentityUnresolvedError(
                    platform=requested_platform,
                    requested_identifier=(
                        selection.identity.identifier
                    ),
                )

            if not identifiers_equal(
                observed_identifier,
                selection.identity.identifier,
            ):
                raise RequestedIdentityMismatchError(
                    platform=requested_platform,
                    requested_identifier=(
                        selection.identity.identifier
                    ),
                    observed_identifier=(
                        observed_identifier
                    ),
                )

    physical_identity = GenericHashAdapter().identify(
        path
    )

    if platform_detection is None:
        platform_detection = detector.detect(
            path
        )

    provider_name = str(
        getattr(
            resolver,
            "name",
            type(resolver).__name__,
        )
    )

    try:
        physical_match = resolver.identify(
            physical_identity
        )
    except ResolverUnavailableError as exc:
        physical_match = None
        physical_lookup = ProviderLookupOutcome(
            status=ProviderLookupStatus.UNAVAILABLE,
            reason=str(exc),
        )
    else:
        physical_lookup = ProviderLookupOutcome(
            status=(
                ProviderLookupStatus.MATCHED
                if physical_match is not None
                else ProviderLookupStatus.NO_MATCH
            )
        )

    normalized_content = None
    physical_representation = None
    local_metadata = None
    normalized_match = None
    normalized_lookup = ProviderLookupOutcome()

    if inspector is not None:
        if inspection_result is None:
            inspection_result = inspector.inspect(
                path
            )

        if inspection_result is not None:
            if not isinstance(
                inspection_result,
                StructuralInspectionResult,
            ):
                raise InspectionContractError(
                    (
                        "inspector inspect() must return "
                        "StructuralInspectionResult or None"
                    ),
                    component=type(inspector).__name__,
                    operation="inspect",
                )

            physical_representation = (
                inspection_result.physical_representation
            )

            if (
                physical_representation is not None
                and not isinstance(
                    physical_representation,
                    RepresentationIdentity,
                )
            ):
                raise InspectionContractError(
                    (
                        "inspector physical_representation must be "
                        "RepresentationIdentity or None"
                    ),
                    component=type(inspector).__name__,
                    operation="inspect",
                    field="physical_representation",
                )

            local_metadata = inspection_result.local_metadata

            if (
                local_metadata is not None
                and not isinstance(
                    local_metadata,
                    LocalContentMetadata,
                )
            ):
                raise InspectionContractError(
                    (
                        "inspector local_metadata must be "
                        "LocalContentMetadata or None"
                    ),
                    component=type(inspector).__name__,
                    operation="inspect",
                    field="local_metadata",
                )

    should_normalize = _should_normalize(
        normalizer=normalizer,
        force_normalization=force_normalization,
        physical_match=physical_match,
        physical_lookup=physical_lookup,
        platform_detection=platform_detection,
        local_metadata=local_metadata,
    )

    if should_normalize:
        try:
            normalized_result = normalizer.identify(path)
        except NoSupportingNormalizerError:
            normalized_result = None

        if normalized_result is not None:
            if not isinstance(
                normalized_result,
                NormalizationResult,
            ):
                raise NormalizerContractError(
                    (
                        "normalizer identify() must return a "
                        "NormalizationResult-compatible object"
                    ),
                    component=type(normalizer).__name__,
                    operation="identify",
                )

            normalized_content = normalized_result.content

            if not isinstance(
                normalized_content,
                NormalizedContentIdentity,
            ):
                raise NormalizerContractError(
                    (
                        "normalizer content must be "
                        "NormalizedContentIdentity"
                    ),
                    component=type(normalizer).__name__,
                    operation="identify",
                    field="content",
                )

            normalized_representation = (
                normalized_result.physical_representation
            )

            if (
                normalized_representation is not None
                and not isinstance(
                    normalized_representation,
                    RepresentationIdentity,
                )
            ):
                raise NormalizerContractError(
                    (
                        "normalizer physical_representation must be "
                        "RepresentationIdentity or None"
                    ),
                    component=type(normalizer).__name__,
                    operation="identify",
                    field="physical_representation",
                )

            normalized_local_metadata = (
                normalized_result.local_metadata
            )

            if (
                normalized_local_metadata is not None
                and not isinstance(
                    normalized_local_metadata,
                    LocalContentMetadata,
                )
            ):
                raise NormalizerContractError(
                    (
                        "normalizer local_metadata must be "
                        "LocalContentMetadata or None"
                    ),
                    component=type(normalizer).__name__,
                    operation="identify",
                    field="local_metadata",
                )

            physical_representation = _merge_structural_evidence(
                physical_representation,
                normalized_representation,
                field="physical_representation",
            )
            local_metadata = _merge_structural_evidence(
                local_metadata,
                normalized_local_metadata,
                field="local_metadata",
            )

            lookup = LookupIdentity(
                file_name=physical_identity.file_name or path.name,
                file_size=physical_identity.file_size
                if physical_identity.file_size is not None
                else path.stat().st_size,
                hashes=normalized_content.hashes,
            )

            try:
                normalized_match = resolver.identify_lookup(
                    lookup
                )
            except ResolverUnavailableError as exc:
                normalized_match = None
                normalized_lookup = ProviderLookupOutcome(
                    status=(
                        ProviderLookupStatus.UNAVAILABLE
                    ),
                    reason=str(exc),
                )
            else:
                normalized_lookup = ProviderLookupOutcome(
                    status=(
                        ProviderLookupStatus.MATCHED
                        if normalized_match is not None
                        else ProviderLookupStatus.NO_MATCH
                    )
                )

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

    requested_identity_assessment = (
        _assess_requested_identity(
            selection=selection,
            platform_detection=platform_detection,
            local_metadata=local_metadata,
        )
    )

    return IdentificationResult(
        physical_identity=physical_identity,
        platform_detection=platform_detection,
        physical_match=physical_match,
        normalized_content=normalized_content,
        physical_representation=physical_representation,
        local_metadata=local_metadata,
        normalized_match=normalized_match,
        release_reconciliation=release_reconciliation,
        platform_reconciliation=reconciliation,
        physical_lookup=physical_lookup,
        normalized_lookup=normalized_lookup,
        provider_name=provider_name,
        requested_identity=(
            requested_identity_assessment
        ),
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
