from rom_metadata_framework.canonical import (
    CanonicalReleaseIdentity,
    IdentificationEvidence,
)
from rom_metadata_framework.identification import (
    IdentificationVerification,
)
from rom_metadata_framework.naming import (
    NamingPolicy,
    sanitize_filename_component,
)
from rom_metadata_framework.verification import (
    VerificationReport,
    VerificationStatus,
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


def verification(
    *,
    physical: VerificationStatus | None = None,
    normalized: VerificationStatus | None = None,
) -> IdentificationVerification:
    def report(
        status: VerificationStatus | None,
    ) -> VerificationReport | None:
        if status is None:
            return None

        return VerificationReport(status=status)

    return IdentificationVerification(
        physical=report(physical),
        normalized=report(normalized),
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
        verification=verification(
            physical=VerificationStatus.KNOWN_GOOD,
        ),
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
        verification=verification(
            physical=VerificationStatus.KNOWN_GOOD,
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
        verification=verification(
            physical=VerificationStatus.KNOWN_GOOD,
        ),
    )

    assert plan.operation == "copy"


def test_rename_plan_can_request_replace() -> None:
    plan = NamingPolicy().plan_rename(
        "unknown.sfc",
        verified_identity(),
        verification=verification(
            physical=VerificationStatus.KNOWN_GOOD,
        ),
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

def test_authoritative_identity_without_verification_is_not_safe() -> None:
    plan = NamingPolicy().plan_rename(
        "unknown.sfc",
        verified_identity(),
    )

    assert not plan.safe_to_apply
    assert not plan.content_known_good
    assert not plan.representation_known_good


def test_normalized_known_good_content_is_safe_for_canonical_name() -> None:
    plan = NamingPolicy().plan_rename(
        "compressed-copy.rvz",
        verified_identity(),
        verification=verification(
            normalized=VerificationStatus.KNOWN_GOOD,
        ),
    )

    assert plan.safe_to_apply
    assert plan.content_known_good
    assert not plan.representation_known_good

    # Normalized content trust authorizes the canonical release
    # name, but does not imply a representation conversion.
    assert (
        plan.destination_name
        == "Super Mario World (USA).rvz"
    )


def test_physical_known_good_marks_representation_known_good() -> None:
    plan = NamingPolicy().plan_rename(
        "unknown.sfc",
        verified_identity(),
        verification=verification(
            physical=VerificationStatus.KNOWN_GOOD,
        ),
    )

    assert plan.safe_to_apply
    assert plan.content_known_good
    assert plan.representation_known_good


def test_verification_conflict_blocks_canonical_naming() -> None:
    conflict_report = VerificationReport(
        status=VerificationStatus.CONFLICT,
        conflicts=("provider evidence conflicts",),
    )

    plan = NamingPolicy().plan_rename(
        "unknown.sfc",
        verified_identity(),
        verification=IdentificationVerification(
            physical=VerificationReport(
                status=VerificationStatus.KNOWN_GOOD,
            ),
            normalized=conflict_report,
        ),
    )

    assert not plan.safe_to_apply
    assert plan.content_known_good
    assert plan.conflicts == (
        "provider evidence conflicts",
    )
