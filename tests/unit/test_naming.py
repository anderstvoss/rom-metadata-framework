from rom_metadata_framework.canonical import (
    CanonicalReleaseIdentity,
    IdentificationEvidence,
)
from rom_metadata_framework.naming import (
    NamingPolicy,
    sanitize_filename_component,
)


def verified_identity(
    *,
    conflicts: tuple[str, ...] = (),
) -> CanonicalReleaseIdentity:
    return CanonicalReleaseIdentity(
        title="Super Mario World",
        release_name="Super Mario World (USA)",
        platform="Super Nintendo Entertainment System",
        source="playmatch",
        source_id="game-id",
        evidence=(
            IdentificationEvidence(
                source="playmatch",
                method="SHA1",
                authoritative=True,
            ),
        ),
        conflicts=conflicts,
    )


def test_canonical_filename_preserves_extension() -> None:
    filename = NamingPolicy().canonical_filename(
        verified_identity(),
        extension="sfc",
    )

    assert filename == "Super Mario World (USA).sfc"


def test_rename_plan_ignores_unreadable_source_name() -> None:
    plan = NamingPolicy().plan_rename(
        "x7q9__unreadable_name__.sfc",
        verified_identity(),
    )

    assert plan.source_name == "x7q9__unreadable_name__.sfc"
    assert plan.destination_name == "Super Mario World (USA).sfc"
    assert plan.reason == "canonical-release-name"
    assert plan.safe_to_apply


def test_conflicted_identity_is_not_safe_to_rename() -> None:
    plan = NamingPolicy().plan_rename(
        "unknown.sfc",
        verified_identity(
            conflicts=("header conflicts with content identity",),
        ),
    )

    assert not plan.safe_to_apply
    assert plan.conflicts == (
        "header conflicts with content identity",
    )


def test_non_authoritative_match_is_not_safe_to_rename() -> None:
    identity = CanonicalReleaseIdentity(
        title="Example",
        release_name="Example (USA)",
        platform="Example System",
        source="playmatch",
        source_id="1",
        evidence=(
            IdentificationEvidence(
                source="playmatch",
                method="FileNameAndSize",
                authoritative=False,
            ),
        ),
    )

    plan = NamingPolicy().plan_rename(
        "Example maybe.sfc",
        identity,
    )

    assert not plan.safe_to_apply


def test_filename_sanitization() -> None:
    assert (
        sanitize_filename_component('Game: Part / One?')
        == "Game_ Part _ One_"
    )


def test_rename_plan_defaults_to_copy() -> None:
    plan = NamingPolicy().plan_rename(
        "unknown.sfc",
        verified_identity(),
    )

    assert plan.operation == "copy"


def test_rename_plan_can_request_replace() -> None:
    plan = NamingPolicy().plan_rename(
        "unknown.sfc",
        verified_identity(),
        operation="replace",
    )

    assert plan.operation == "replace"


def test_rename_plan_rejects_unknown_operation() -> None:
    import pytest

    with pytest.raises(ValueError):
        NamingPolicy().plan_rename(
            "unknown.sfc",
            verified_identity(),
            operation="delete-source",
        )
