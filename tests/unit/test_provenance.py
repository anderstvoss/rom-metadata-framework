from rom_metadata_framework.provenance import CatalogueEvidence


def test_catalogue_evidence_normalizes_fields() -> None:
    evidence = CatalogueEvidence(
        source=" Playmatch ",
        match_method="sha1",
        authority=" No-Intro ",
        catalogue_name=" Nintendo - SNES ",
        file_status=" Verified ",
        current_in_latest_catalogue=True,
        hashes={" SHA1 ": " ABCDEF "},
    )

    assert evidence.source == "playmatch"
    assert evidence.match_method == "SHA1"
    assert evidence.authority == "No-Intro"
    assert evidence.file_status == "verified"
    assert evidence.hashes == {"sha1": "abcdef"}


def test_sha1_is_strong_content_match() -> None:
    evidence = CatalogueEvidence(
        source="test",
        match_method="SHA1",
    )

    assert evidence.is_content_match
    assert evidence.is_strong_content_match


def test_crc_is_content_match_but_not_strong() -> None:
    evidence = CatalogueEvidence(
        source="test",
        match_method="CRC",
    )

    assert evidence.is_content_match
    assert not evidence.is_strong_content_match
