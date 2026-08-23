from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .canonical import CanonicalReleaseIdentity
from .provenance import CatalogueEvidence


class VerificationStatus(StrEnum):
    """Normalized content verification outcome."""

    KNOWN_GOOD = "known_good"
    KNOWN_BAD = "known_bad"
    CATALOGUE_MATCH = "catalogue_match"
    CONFLICT = "conflict"
    PROBABLE = "probable"
    UNKNOWN = "unknown"


_BAD_STATUSES = frozenset({
    "bad",
    "bad dump",
    "baddump",
    "corrupt",
    "corrupted",
})


@dataclass(frozen=True, slots=True)
class VerificationReport:
    """Provider-independent assessment of identified content."""

    status: VerificationStatus
    evidence: tuple[CatalogueEvidence, ...] = ()
    reasons: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()

    @property
    def known_good(self) -> bool:
        return self.status is VerificationStatus.KNOWN_GOOD


def verify_release(
    identity: CanonicalReleaseIdentity,
) -> VerificationReport:
    """Derive a conservative verification result from available evidence."""

    evidence = identity.catalogue_evidence

    if identity.conflicts:
        return VerificationReport(
            status=VerificationStatus.CONFLICT,
            evidence=evidence,
            reasons=(
                "strong identity evidence contains unresolved conflicts",
            ),
            conflicts=identity.conflicts,
        )

    for item in evidence:
        if (
            item.is_content_match
            and item.file_status in _BAD_STATUSES
        ):
            return VerificationReport(
                status=VerificationStatus.KNOWN_BAD,
                evidence=evidence,
                reasons=(
                    "content exactly matches a catalogue record "
                    "classified as bad",
                ),
            )

    for item in evidence:
        if (
            item.is_strong_content_match
            and item.is_verified
            and item.current_in_latest_catalogue is True
            and item.authority is not None
            and item.catalogue_name is not None
        ):
            return VerificationReport(
                status=VerificationStatus.KNOWN_GOOD,
                evidence=evidence,
                reasons=(
                    "strong content hash matches a verified file "
                    "in the current catalogue",
                ),
            )

    if any(item.is_content_match for item in evidence):
        return VerificationReport(
            status=VerificationStatus.CATALOGUE_MATCH,
            evidence=evidence,
            reasons=(
                "content matches a catalogue record but does not "
                "meet the known-good policy",
            ),
        )

    if identity.evidence:
        return VerificationReport(
            status=VerificationStatus.PROBABLE,
            evidence=evidence,
            reasons=(
                "identity evidence exists without qualifying "
                "catalogue verification",
            ),
        )

    return VerificationReport(
        status=VerificationStatus.UNKNOWN,
        evidence=evidence,
        reasons=("insufficient verification evidence",),
    )
