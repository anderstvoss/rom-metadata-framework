from rom_metadata_framework.canonical import (
    CanonicalReleaseIdentity,
    IdentificationEvidence,
)
from rom_metadata_framework.provenance import CatalogueEvidence
from rom_metadata_framework.verification import (
    VerificationStatus,
    verify_release,
)


def identity_with(
    catalogue: CatalogueEvidence,
    *,
    conflicts: tuple[str, ...] = (),
) -> CanonicalReleaseIdentity:
    return CanonicalReleaseIdentity(
        release_name="Example (USA)",
        platform="snes",
        source="test",
        source_id="1",
        evidence=(
            IdentificationEvidence(
                source="test",
                method=catalogue.match_method,
                authoritative=True,
            ),
        ),
        catalogue_evidence=(catalogue,),
        conflicts=conflicts,
    )


def test_verified_current_sha1_is_known_good() -> None:
    report = verify_release(
        identity_with(
            CatalogueEvidence(
                source="playmatch",
                match_method="SHA1",
                authority="No-Intro",
                catalogue_name="Nintendo - SNES",
                catalogue_version="20260614",
                file_status="Verified",
                current_in_latest_catalogue=True,
            )
        )
    )

    assert report.status is VerificationStatus.KNOWN_GOOD
    assert report.known_good


def test_crc_verified_record_is_only_catalogue_match() -> None:
    report = verify_release(
        identity_with(
            CatalogueEvidence(
                source="playmatch",
                match_method="CRC",
                authority="No-Intro",
                catalogue_name="Nintendo - SNES",
                file_status="Verified",
                current_in_latest_catalogue=True,
            )
        )
    )

    assert report.status is VerificationStatus.CATALOGUE_MATCH


def test_historical_verified_record_is_not_known_good() -> None:
    report = verify_release(
        identity_with(
            CatalogueEvidence(
                source="playmatch",
                match_method="SHA1",
                authority="No-Intro",
                catalogue_name="Nintendo - SNES",
                file_status="Verified",
                current_in_latest_catalogue=False,
            )
        )
    )

    assert report.status is VerificationStatus.CATALOGUE_MATCH


def test_bad_catalogue_record_is_known_bad() -> None:
    report = verify_release(
        identity_with(
            CatalogueEvidence(
                source="catalogue",
                match_method="SHA1",
                authority="Example",
                catalogue_name="Example DAT",
                file_status="Bad",
                current_in_latest_catalogue=True,
            )
        )
    )

    assert report.status is VerificationStatus.KNOWN_BAD


def test_conflict_overrides_known_good() -> None:
    report = verify_release(
        identity_with(
            CatalogueEvidence(
                source="playmatch",
                match_method="SHA1",
                authority="No-Intro",
                catalogue_name="Nintendo - SNES",
                file_status="Verified",
                current_in_latest_catalogue=True,
            ),
            conflicts=("header identifies another release",),
        )
    )

    assert report.status is VerificationStatus.CONFLICT
