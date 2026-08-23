"""Stable consumer-facing API for rom-metadata-framework."""

from .canonical import CanonicalReleaseIdentity
from .capability import (
    RuntimeCapability,
    RuntimeCapabilityStatus,
)
from .content import NormalizedContentIdentity
from .detection import (
    PlatformCandidate,
    PlatformDetection,
    PlatformEvidence,
)
from .identification import (
    IdentificationResult,
    IdentificationVerification,
    identify_file,
    verify_identification,
)
from .identity import (
    HashSet,
    RomIdentity,
)
from .local_metadata import (
    LocalContentMetadata,
    LocalIdentifier,
    LocalMetadataProvenance,
    LocalMetadataValue,
    LocalPlayerCount,
    LocalTimestamp,
)
from .metadata import (
    AgeRating,
    ExternalIdentifier,
    MediaReference,
    MetadataProvenance,
    MetadataValue,
    PlayerCount,
    ReleaseDate,
    ReleaseMetadata,
)
from .metadata_collection import (
    MetadataEnrichmentResult,
    collect_identification_metadata,
)
from .metadata_reconciliation import (
    MetadataFieldReconciliation,
    MetadataFieldReconciliationStatus,
    MetadataReconciliationReport,
)
from .naming import (
    NamingPolicy,
    RenamePlan,
)
from .platforms import (
    PlatformDefinition,
    UnknownPlatformError,
    UnsupportedPlatformBackendError,
    canonical_platform_name,
    resolve_platform,
)
from .reconciliation import (
    PlatformReconciliation,
    PlatformReconciliationStatus,
)
from .release_reconciliation import (
    ReleaseReconciliation,
    ReleaseReconciliationStatus,
)
from .representation import RepresentationIdentity
from .verification import (
    DEFAULT_VERIFICATION_POLICY,
    VerificationPolicy,
    VerificationReport,
    VerificationStatus,
)

__all__ = (
    "DEFAULT_VERIFICATION_POLICY",
    "AgeRating",
    "CanonicalReleaseIdentity",
    "ExternalIdentifier",
    "HashSet",
    "IdentificationResult",
    "IdentificationVerification",
    "LocalContentMetadata",
    "LocalIdentifier",
    "LocalMetadataProvenance",
    "LocalMetadataValue",
    "LocalPlayerCount",
    "LocalTimestamp",
    "MediaReference",
    "MetadataEnrichmentResult",
    "MetadataFieldReconciliation",
    "MetadataFieldReconciliationStatus",
    "MetadataProvenance",
    "MetadataReconciliationReport",
    "MetadataValue",
    "NamingPolicy",
    "NormalizedContentIdentity",
    "PlatformCandidate",
    "PlatformDefinition",
    "PlatformDetection",
    "PlatformEvidence",
    "PlatformReconciliation",
    "PlatformReconciliationStatus",
    "PlayerCount",
    "ReleaseDate",
    "ReleaseMetadata",
    "ReleaseReconciliation",
    "ReleaseReconciliationStatus",
    "RenamePlan",
    "RepresentationIdentity",
    "RomIdentity",
    "RuntimeCapability",
    "RuntimeCapabilityStatus",
    "UnknownPlatformError",
    "UnsupportedPlatformBackendError",
    "VerificationPolicy",
    "VerificationReport",
    "VerificationStatus",
    "canonical_platform_name",
    "collect_identification_metadata",
    "identify_file",
    "resolve_platform",
    "verify_identification",
)
