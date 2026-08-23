from rom_metadata_framework.canonical import CanonicalReleaseIdentity
from rom_metadata_framework.release_reconciliation import (
    ReleaseReconciliationStatus,
    reconcile_release_matches,
)


def release(
    name: str = "Example Game (USA)",
    *,
    platform: str = "nes",
    source: str = "provider-a",
    source_id: str = "1",
) -> CanonicalReleaseIdentity:
    return CanonicalReleaseIdentity(
        release_name=name,
        platform=platform,
        source=source,
        source_id=source_id,
    )


def test_no_matches_are_unresolved() -> None:
    result = reconcile_release_matches(None, None)

    assert result.status is ReleaseReconciliationStatus.UNRESOLVED
    assert result.selected is None
    assert not result.has_conflict


def test_physical_only_selects_physical() -> None:
    physical = release()

    result = reconcile_release_matches(physical, None)

    assert result.status is ReleaseReconciliationStatus.PHYSICAL_ONLY
    assert result.selected is physical
    assert not result.has_conflict


def test_normalized_only_selects_normalized() -> None:
    normalized = release()

    result = reconcile_release_matches(None, normalized)

    assert result.status is ReleaseReconciliationStatus.NORMALIZED_ONLY
    assert result.selected is normalized
    assert not result.has_conflict


def test_same_release_agrees() -> None:
    physical = release()
    normalized = release()

    result = reconcile_release_matches(physical, normalized)

    assert result.status is ReleaseReconciliationStatus.AGREEMENT
    assert result.selected is physical
    assert not result.has_conflict


def test_same_release_may_use_different_catalogue_records() -> None:
    physical = release(
        source="headered-catalogue",
        source_id="headered-123",
    )
    normalized = release(
        source="headerless-catalogue",
        source_id="headerless-456",
    )

    result = reconcile_release_matches(physical, normalized)

    assert result.status is ReleaseReconciliationStatus.AGREEMENT
    assert result.selected is physical
    assert not result.has_conflict


def test_different_platforms_are_conflict() -> None:
    physical = release(platform="nes")
    normalized = release(platform="snes")

    result = reconcile_release_matches(physical, normalized)

    assert result.status is ReleaseReconciliationStatus.PLATFORM_CONFLICT
    assert result.selected is None
    assert result.has_conflict
    assert result.conflicts


def test_different_releases_on_same_platform_are_conflict() -> None:
    physical = release("Example Game (USA)")
    normalized = release("Different Game (USA)")

    result = reconcile_release_matches(physical, normalized)

    assert result.status is ReleaseReconciliationStatus.RELEASE_CONFLICT
    assert result.selected is None
    assert result.has_conflict
    assert result.conflicts
