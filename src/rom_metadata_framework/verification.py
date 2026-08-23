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
class VerificationPolicy:
    """Policy controlling which catalogue evidence may establish trust."""

    trusted_authorities: frozenset[str] = frozenset({
        "no-intro",
        "redump",
    })
    accepted_verified_statuses: frozenset[str] = frozenset({
        "verified",
    })
    require_current_catalogue: bool = True

    def __post_init__(self) -> None:
        normalized_authorities = frozenset(
            authority.strip().lower()
            for authority in self.trusted_authorities
            if authority.strip()
        )

        normalized_statuses = frozenset(
            status.strip().lower()
            for status in self.accepted_verified_statuses
            if status.strip()
        )

        object.__setattr__(
            self,
            "trusted_authorities",
            normalized_authorities,
        )
        object.__setattr__(
            self,
            "accepted_verified_statuses",
            normalized_statuses,
        )

    def trusts_authority(self, authority: str | None) -> bool:
        if authority is None:
            return False

        return authority.strip().lower() in self.trusted_authorities

    def accepts_status(self, status: str | None) -> bool:
        if status is None:
            return False

        return status.strip().lower() in self.accepted_verified_statuses


DEFAULT_VERIFICATION_POLICY = VerificationPolicy()


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
    *,
    policy: VerificationPolicy = DEFAULT_VERIFICATION_POLICY,
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
        current_ok = (
            item.current_in_latest_catalogue is True
            or not policy.require_current_catalogue
        )

        if (
            item.is_strong_content_match
            and policy.accepts_status(item.file_status)
            and current_ok
            and policy.trusts_authority(item.authority)
            and item.catalogue_name is not None
        ):
            return VerificationReport(
                status=VerificationStatus.KNOWN_GOOD,
                evidence=evidence,
                reasons=(
                    "strong content hash matches an accepted file "
                    "from a trusted catalogue authority",
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
