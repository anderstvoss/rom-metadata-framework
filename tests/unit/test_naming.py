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


def identification_result(
    *,
    title: str | None = "Example Game",
    release_name: str = "Example Game (USA)",
    platform: str = "wii",
    local_metadata=None,
):
    from rom_metadata_framework.detection import (
        PlatformDetection,
    )
    from rom_metadata_framework.identification import (
        IdentificationResult,
    )
    from rom_metadata_framework.identity import RomIdentity

    canonical = CanonicalReleaseIdentity(
        title=title,
        release_name=release_name,
        platform=platform,
        source="playmatch",
        source_id="game-id",
    )

    return IdentificationResult(
        physical_identity=RomIdentity(
            file_name="input.rom",
            file_size=1,
        ),
        platform_detection=PlatformDetection(),
        physical_match=canonical,
        local_metadata=local_metadata,
    )


def test_structured_naming_input_uses_clean_canonical_title() -> None:
    from rom_metadata_framework.local_metadata import (
        LocalContentMetadata,
        LocalIdentifier,
        LocalMetadataProvenance,
        LocalMetadataValue,
    )
    from rom_metadata_framework.naming import (
        naming_input_from_identification,
    )

    provenance = LocalMetadataProvenance(
        source="synthetic",
        method="fixture",
    )

    result = identification_result(
        local_metadata=LocalContentMetadata(
            platform="wii",
            identifiers=(
                LocalIdentifier(
                    namespace="nintendo-game-id",
                    value="ABCE01",
                    provenance=provenance,
                ),
            ),
            countries=(
                LocalMetadataValue(
                    value="USA",
                    provenance=provenance,
                ),
            ),
            release_revisions=(
                LocalMetadataValue(
                    value="2",
                    provenance=provenance,
                ),
            ),
        ),
    )

    naming = naming_input_from_identification(
        result
    )

    assert naming.title == "Example Game"
    assert naming.title_is_structured
    assert naming.primary_identifier == "ABCE01"
    assert naming.region == "USA"
    assert naming.revision == "2"


def test_structured_filename_uses_selected_fields() -> None:
    from rom_metadata_framework.naming import (
        NamingInput,
    )

    filename = NamingPolicy().structured_filename(
        NamingInput(
            title="Example Game",
            title_is_structured=True,
            platform="wii",
            primary_identifier="ABCE01",
            region="USA",
            revision="2",
        ),
        extension="rvz",
    )

    assert (
        filename
        == "Example Game [ABCE01] (USA) (Rev 2).rvz"
    )


def test_release_name_fallback_does_not_duplicate_qualifiers() -> None:
    from rom_metadata_framework.local_metadata import (
        LocalContentMetadata,
        LocalIdentifier,
        LocalMetadataProvenance,
        LocalMetadataValue,
    )
    from rom_metadata_framework.naming import (
        naming_input_from_identification,
    )

    provenance = LocalMetadataProvenance(
        source="synthetic",
        method="fixture",
    )

    result = identification_result(
        title=None,
        release_name="Example Game (USA) (En,Fr)",
        local_metadata=LocalContentMetadata(
            platform="wii",
            identifiers=(
                LocalIdentifier(
                    namespace="nintendo-game-id",
                    value="ABCE01",
                    provenance=provenance,
                ),
            ),
            countries=(
                LocalMetadataValue(
                    value="USA",
                    provenance=provenance,
                ),
            ),
            release_revisions=(
                LocalMetadataValue(
                    value="2",
                    provenance=provenance,
                ),
            ),
        ),
    )

    naming = naming_input_from_identification(
        result
    )

    assert not naming.title_is_structured
    assert naming.title == "Example Game (USA) (En,Fr)"
    assert naming.primary_identifier == "ABCE01"
    assert naming.region is None
    assert naming.revision is None

    filename = NamingPolicy().structured_filename(
        naming,
        extension="rvz",
    )

    assert (
        filename
        == "Example Game (USA) (En,Fr) [ABCE01].rvz"
    )


def test_revision_zero_is_omitted_from_structured_naming() -> None:
    from rom_metadata_framework.local_metadata import (
        LocalContentMetadata,
        LocalMetadataProvenance,
        LocalMetadataValue,
    )
    from rom_metadata_framework.naming import (
        naming_input_from_identification,
    )

    provenance = LocalMetadataProvenance(
        source="synthetic",
        method="fixture",
    )

    result = identification_result(
        local_metadata=LocalContentMetadata(
            platform="wii",
            release_revisions=(
                LocalMetadataValue(
                    value="0",
                    provenance=provenance,
                ),
            ),
        ),
    )

    naming = naming_input_from_identification(
        result
    )

    assert naming.revision is None


def test_disc_qualifier_requires_explicit_multi_disc_total() -> None:
    from rom_metadata_framework.local_metadata import (
        LocalContentMetadata,
        LocalMetadataProvenance,
        LocalMetadataValue,
    )
    from rom_metadata_framework.naming import (
        naming_input_from_identification,
    )

    provenance = LocalMetadataProvenance(
        source="synthetic",
        method="fixture",
    )

    result = identification_result(
        local_metadata=LocalContentMetadata(
            platform="wii",
            disc_numbers=(
                LocalMetadataValue(
                    value=1,
                    provenance=provenance,
                ),
            ),
        ),
    )

    naming = naming_input_from_identification(
        result
    )

    assert naming.disc_number is None
    assert naming.disc_total is None


def test_explicit_multi_disc_metadata_is_rendered() -> None:
    from rom_metadata_framework.local_metadata import (
        LocalContentMetadata,
        LocalMetadataProvenance,
        LocalMetadataValue,
    )
    from rom_metadata_framework.naming import (
        naming_input_from_identification,
    )

    provenance = LocalMetadataProvenance(
        source="synthetic",
        method="fixture",
    )

    result = identification_result(
        local_metadata=LocalContentMetadata(
            platform="wii",
            disc_numbers=(
                LocalMetadataValue(
                    value=1,
                    provenance=provenance,
                ),
            ),
            disc_totals=(
                LocalMetadataValue(
                    value=2,
                    provenance=provenance,
                ),
            ),
        ),
    )

    naming = naming_input_from_identification(
        result
    )

    assert naming.disc_number == 1
    assert naming.disc_total == 2

    assert (
        NamingPolicy().structured_filename(
            naming,
            extension="iso",
        )
        == "Example Game (Disc 1 of 2).iso"
    )


def test_structured_naming_uses_raw_xbox_title_id() -> None:
    from rom_metadata_framework.local_metadata import (
        LocalContentMetadata,
        LocalIdentifier,
        LocalMetadataProvenance,
    )
    from rom_metadata_framework.naming import (
        naming_input_from_identification,
    )

    provenance = LocalMetadataProvenance(
        source="synthetic",
        method="fixture",
    )

    result = identification_result(
        platform="xbox",
        local_metadata=LocalContentMetadata(
            platform="xbox",
            identifiers=(
                LocalIdentifier(
                    namespace="xbox-title-id",
                    value="4D530004",
                    provenance=provenance,
                ),
                LocalIdentifier(
                    namespace="xbox-title-id-formatted",
                    value="MS-004",
                    provenance=provenance,
                ),
            ),
        ),
    )

    naming = naming_input_from_identification(
        result
    )

    assert naming.primary_identifier == "4D530004"


def test_structured_naming_requires_canonical_release() -> None:
    import pytest

    from rom_metadata_framework.detection import (
        PlatformDetection,
    )
    from rom_metadata_framework.identification import (
        IdentificationResult,
    )
    from rom_metadata_framework.identity import RomIdentity
    from rom_metadata_framework.naming import (
        naming_input_from_identification,
    )

    result = IdentificationResult(
        physical_identity=RomIdentity(
            file_name="input.rom",
            file_size=1,
        ),
        platform_detection=PlatformDetection(),
    )

    with pytest.raises(
        ValueError,
        match="canonical release identity is required",
    ):
        naming_input_from_identification(result)


def test_plan_identification_rename_preserves_existing_safety_policy() -> None:
    from rom_metadata_framework.local_metadata import (
        LocalContentMetadata,
        LocalIdentifier,
        LocalMetadataProvenance,
        LocalMetadataValue,
    )

    provenance = LocalMetadataProvenance(
        source="synthetic",
        method="fixture",
    )

    result = identification_result(
        local_metadata=LocalContentMetadata(
            platform="wii",
            identifiers=(
                LocalIdentifier(
                    namespace="nintendo-game-id",
                    value="ABCE01",
                    provenance=provenance,
                ),
            ),
            countries=(
                LocalMetadataValue(
                    value="USA",
                    provenance=provenance,
                ),
            ),
        ),
    )

    plan = NamingPolicy().plan_identification_rename(
        "unreadable-source.rvz",
        result,
        verification=verification(
            physical=VerificationStatus.KNOWN_GOOD,
        ),
    )

    assert (
        plan.destination_name
        == "Example Game [ABCE01] (USA).rvz"
    )
    assert plan.reason == "structured-identification"
    assert plan.safe_to_apply
    assert plan.operation == "copy"


def test_structured_naming_ignores_conflicting_local_platform() -> None:
    from rom_metadata_framework.local_metadata import (
        LocalContentMetadata,
        LocalIdentifier,
        LocalMetadataProvenance,
        LocalMetadataValue,
    )
    from rom_metadata_framework.naming import (
        naming_input_from_identification,
    )

    provenance = LocalMetadataProvenance(
        source="synthetic",
        method="fixture",
    )

    result = identification_result(
        platform="wii",
        local_metadata=LocalContentMetadata(
            platform="ps3",
            identifiers=(
                LocalIdentifier(
                    namespace="nintendo-game-id",
                    value="ABCE01",
                    provenance=provenance,
                ),
            ),
            countries=(
                LocalMetadataValue(
                    value="USA",
                    provenance=provenance,
                ),
            ),
            release_revisions=(
                LocalMetadataValue(
                    value="2",
                    provenance=provenance,
                ),
            ),
            disc_numbers=(
                LocalMetadataValue(
                    value=1,
                    provenance=provenance,
                ),
            ),
            disc_totals=(
                LocalMetadataValue(
                    value=2,
                    provenance=provenance,
                ),
            ),
        ),
    )

    naming = naming_input_from_identification(
        result
    )

    assert naming.title == "Example Game"
    assert naming.title_is_structured
    assert naming.platform == "wii"
    assert naming.primary_identifier is None
    assert naming.region is None
    assert naming.revision is None
    assert naming.disc_number is None
    assert naming.disc_total is None

    assert (
        NamingPolicy().structured_filename(
            naming,
            extension="rvz",
        )
        == "Example Game.rvz"
    )


def test_structured_naming_ignores_unscoped_local_metadata() -> None:
    from rom_metadata_framework.local_metadata import (
        LocalContentMetadata,
        LocalIdentifier,
        LocalMetadataProvenance,
        LocalMetadataValue,
    )
    from rom_metadata_framework.naming import (
        naming_input_from_identification,
    )

    provenance = LocalMetadataProvenance(
        source="synthetic",
        method="fixture",
    )

    result = identification_result(
        platform="wii",
        local_metadata=LocalContentMetadata(
            identifiers=(
                LocalIdentifier(
                    namespace="nintendo-game-id",
                    value="ABCE01",
                    provenance=provenance,
                ),
            ),
            countries=(
                LocalMetadataValue(
                    value="USA",
                    provenance=provenance,
                ),
            ),
        ),
    )

    naming = naming_input_from_identification(
        result
    )

    assert naming.primary_identifier is None
    assert naming.region is None
