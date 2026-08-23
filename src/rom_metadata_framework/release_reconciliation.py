from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .canonical import CanonicalReleaseIdentity


class ReleaseReconciliationStatus(StrEnum):
    """Relationship between physical and normalized provider matches."""

    AGREEMENT = "agreement"
    PHYSICAL_ONLY = "physical_only"
    NORMALIZED_ONLY = "normalized_only"
    PLATFORM_CONFLICT = "platform_conflict"
    RELEASE_CONFLICT = "release_conflict"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class ReleaseReconciliation:
    """Comparison of physical and normalized canonical matches."""

    status: ReleaseReconciliationStatus
    selected: CanonicalReleaseIdentity | None = None
    physical: CanonicalReleaseIdentity | None = None
    normalized: CanonicalReleaseIdentity | None = None
    conflicts: tuple[str, ...] = ()

    @property
    def has_conflict(self) -> bool:
        return self.status in {
            ReleaseReconciliationStatus.PLATFORM_CONFLICT,
            ReleaseReconciliationStatus.RELEASE_CONFLICT,
        }


def reconcile_release_matches(
    physical: CanonicalReleaseIdentity | None,
    normalized: CanonicalReleaseIdentity | None,
) -> ReleaseReconciliation:
    """Reconcile provider matches without treating catalogue IDs as identity."""

    if physical is None and normalized is None:
        return ReleaseReconciliation(
            status=ReleaseReconciliationStatus.UNRESOLVED,
        )

    if physical is not None and normalized is None:
        return ReleaseReconciliation(
            status=ReleaseReconciliationStatus.PHYSICAL_ONLY,
            selected=physical,
            physical=physical,
        )

    if physical is None and normalized is not None:
        return ReleaseReconciliation(
            status=ReleaseReconciliationStatus.NORMALIZED_ONLY,
            selected=normalized,
            normalized=normalized,
        )

    assert physical is not None
    assert normalized is not None

    if physical.platform != normalized.platform:
        conflict = (
            "physical provider match identifies platform "
            f"{physical.platform!r} but normalized provider match "
            f"identifies {normalized.platform!r}"
        )

        return ReleaseReconciliation(
            status=ReleaseReconciliationStatus.PLATFORM_CONFLICT,
            physical=physical,
            normalized=normalized,
            conflicts=(conflict,),
        )

    if physical.release_name != normalized.release_name:
        conflict = (
            "physical provider match identifies release "
            f"{physical.release_name!r} but normalized provider match "
            f"identifies {normalized.release_name!r}"
        )

        return ReleaseReconciliation(
            status=ReleaseReconciliationStatus.RELEASE_CONFLICT,
            physical=physical,
            normalized=normalized,
            conflicts=(conflict,),
        )

    return ReleaseReconciliation(
        status=ReleaseReconciliationStatus.AGREEMENT,
        selected=physical,
        physical=physical,
        normalized=normalized,
    )
