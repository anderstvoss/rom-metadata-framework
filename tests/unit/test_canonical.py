import pytest

from rom_metadata_framework.canonical import (
    CanonicalReleaseIdentity,
    IdentificationEvidence,
)


def test_evidence_normalizes_fields() -> None:
    evidence = IdentificationEvidence(
        source=" Playmatch ",
        method="SHA1",
        authoritative=True,
        value=" abc ",
        details={" platform ": " SNES "},
    )

    assert evidence.source == "playmatch"
    assert evidence.method == "SHA1"
    assert evidence.value == "abc"
    assert evidence.details == {"platform": "SNES"}


def test_canonical_identity_normalizes_external_ids() -> None:
    identity = CanonicalReleaseIdentity(
        title="Super Mario World",
        release_name="Super Mario World (USA)",
        platform="Super Nintendo Entertainment System",
        source="Playmatch",
        source_id="game-id",
        external_ids={
            " IGDB ": " 1070 ",
            "RetroAchievements": "228",
        },
    )

    assert identity.source == "playmatch"
    assert identity.external_ids == {
        "igdb": "1070",
        "retroachievements": "228",
    }


def test_authoritative_content_match_is_detected() -> None:
    identity = CanonicalReleaseIdentity(
        title="Example",
        release_name="Example (USA)",
        platform="Example System",
        source="playmatch",
        source_id="1",
        evidence=(
            IdentificationEvidence(
                source="playmatch",
                method="SHA1",
                authoritative=True,
            ),
        ),
    )

    assert identity.has_authoritative_content_match


def test_filename_match_is_not_authoritative_content_match() -> None:
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

    assert not identity.has_authoritative_content_match


def test_conflicts_are_exposed() -> None:
    identity = CanonicalReleaseIdentity(
        title="Example",
        release_name="Example",
        platform="Example System",
        source="test",
        source_id="1",
        conflicts=(" header identifies another release ",),
    )

    assert identity.has_conflicts
    assert identity.conflicts == (
        "header identifies another release",
    )


def test_empty_optional_title_normalizes_to_none() -> None:
    identity = CanonicalReleaseIdentity(
        title="   ",
        release_name="Example",
        platform="Example System",
        source="test",
        source_id="1",
    )

    assert identity.title is None


def test_empty_release_name_is_rejected() -> None:
    with pytest.raises(ValueError):
        CanonicalReleaseIdentity(
            release_name="",
            platform="Example System",
            source="test",
            source_id="1",
        )
