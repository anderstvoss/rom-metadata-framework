import json
from io import BytesIO
from typing import Self
from urllib.error import HTTPError

import pytest

from rom_metadata_framework.identity import HashSet, RomIdentity
from rom_metadata_framework.playmatch import (
    PlaymatchRequestError,
    PlaymatchResolver,
    PlaymatchResponseError,
)
from rom_metadata_framework.resolvers import MetadataResolver


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._stream = BytesIO(payload)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._stream.read()


def identity() -> RomIdentity:
    return RomIdentity(
        platform="snes",
        format="sfc",
        file_name="Super Mario World (USA).sfc",
        file_size=524288,
        hashes=HashSet(
            crc32="b19ed489",
            md5="cdd3c8c37322978ca8669b34bc89c804",
            sha1="6b47bb75d16514b6a476aa0c73a683a2a4c18765",
        ),
    )


def test_playmatch_resolver_matches_protocol() -> None:
    assert isinstance(PlaymatchResolver(), MetadataResolver)


def test_playmatch_resolver_returns_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "gameMatchType": "SHA1",
        "game": {
            "id": "11111111-1111-1111-1111-111111111111",
            "name": "Super Mario World",
        },
        "platform": {
            "id": "22222222-2222-2222-2222-222222222222",
            "name": "Super Nintendo Entertainment System",
        },
        "externalMetadata": [
            {
                "providerName": "IGDB",
                "providerId": "1074",
                "matchType": "Automatic",
            },
            {
                "providerName": "RetroAchievements",
                "providerId": "228",
                "matchType": "Automatic",
            },
        ],
    }

    def fake_urlopen(request, timeout):
        assert timeout == 10.0

        url = request.full_url
        assert "/api/v2/identify/relations?" in url
        assert "fileName=Super+Mario+World+%28USA%29.sfc" in url
        assert "fileSize=524288" in url
        assert "sha1=6b47bb75d16514b6a476aa0c73a683a2a4c18765" in url
        assert "md5=cdd3c8c37322978ca8669b34bc89c804" in url
        assert "crc=b19ed489" in url

        return FakeResponse(json.dumps(payload).encode())

    monkeypatch.setattr(
        "rom_metadata_framework.playmatch.urlopen",
        fake_urlopen,
    )

    metadata = PlaymatchResolver().resolve(identity())

    assert metadata is not None
    assert metadata.title == "Super Mario World"
    assert metadata.provider == "playmatch"
    assert metadata.platform == "snes"
    assert metadata.external_ids == {
        "igdb": "1074",
        "retroachievements": "228",
        "playmatch": "11111111-1111-1111-1111-111111111111",
    }


def test_playmatch_resolver_returns_none_for_no_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "gameMatchType": "NoMatch",
        "externalMetadata": [],
    }

    monkeypatch.setattr(
        "rom_metadata_framework.playmatch.urlopen",
        lambda request, timeout: FakeResponse(
            json.dumps(payload).encode()
        ),
    )

    assert PlaymatchResolver().resolve(identity()) is None


def test_playmatch_requires_source_metadata() -> None:
    resolver = PlaymatchResolver()

    with pytest.raises(ValueError):
        resolver.resolve(
            RomIdentity(
                hashes=HashSet(
                    md5="cdd3c8c37322978ca8669b34bc89c804"
                )
            )
        )


def test_playmatch_rejects_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "rom_metadata_framework.playmatch.urlopen",
        lambda request, timeout: FakeResponse(b"not-json"),
    )

    with pytest.raises(PlaymatchResponseError):
        PlaymatchResolver().resolve(identity())


def test_playmatch_rejects_invalid_matched_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "gameMatchType": "SHA1",
        "game": None,
    }

    monkeypatch.setattr(
        "rom_metadata_framework.playmatch.urlopen",
        lambda request, timeout: FakeResponse(
            json.dumps(payload).encode()
        ),
    )

    with pytest.raises(PlaymatchResponseError):
        PlaymatchResolver().resolve(identity())


def test_playmatch_reports_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(request, timeout):
        raise HTTPError(
            request.full_url,
            429,
            "Too Many Requests",
            {},
            None,
        )

    monkeypatch.setattr(
        "rom_metadata_framework.playmatch.urlopen",
        fake_urlopen,
    )

    with pytest.raises(PlaymatchRequestError):
        PlaymatchResolver().resolve(identity())


def test_playmatch_rejects_duplicate_provider_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "gameMatchType": "MD5",
        "game": {
            "id": "11111111-1111-1111-1111-111111111111",
            "name": "Example",
        },
        "externalMetadata": [
            {
                "providerName": "IGDB",
                "providerId": "1",
            },
            {
                "providerName": "IGDB",
                "providerId": "2",
            },
        ],
    }

    monkeypatch.setattr(
        "rom_metadata_framework.playmatch.urlopen",
        lambda request, timeout: FakeResponse(
            json.dumps(payload).encode()
        ),
    )

    with pytest.raises(PlaymatchResponseError):
        PlaymatchResolver().resolve(identity())


def test_playmatch_identify_preserves_match_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "gameMatchType": "SHA1",
        "game": {
            "id": "11111111-1111-1111-1111-111111111111",
            "name": "Super Mario World (USA)",
        },
        "platform": {
            "id": "22222222-2222-2222-2222-222222222222",
            "name": "Super Nintendo Entertainment System",
        },
        "externalMetadata": [
            {
                "providerName": "IGDB",
                "providerId": "1070",
                "matchType": "Automatic",
            },
        ],
    }

    monkeypatch.setattr(
        "rom_metadata_framework.playmatch.urlopen",
        lambda request, timeout: FakeResponse(
            json.dumps(payload).encode()
        ),
    )

    result = PlaymatchResolver().identify(identity())

    assert result is not None
    assert result.release_name == "Super Mario World (USA)"
    assert result.title is None
    assert result.platform == "snes"
    assert result.has_authoritative_content_match
    assert len(result.evidence) == 1
    assert result.evidence[0].source == "playmatch"
    assert result.evidence[0].method == "SHA1"
    assert result.evidence[0].authoritative
    assert result.evidence[0].details["platform"] == "snes"
    assert (
        result.evidence[0].details["provider_platform"]
        == "Super Nintendo Entertainment System"
    )


def test_playmatch_filename_fallback_is_not_authoritative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "gameMatchType": "FileNameAndSize",
        "game": {
            "id": "11111111-1111-1111-1111-111111111111",
            "name": "Example (USA)",
        },
        "platform": {
            "id": "22222222-2222-2222-2222-222222222222",
            "name": "Example System",
        },
        "externalMetadata": [],
    }

    monkeypatch.setattr(
        "rom_metadata_framework.playmatch.urlopen",
        lambda request, timeout: FakeResponse(
            json.dumps(payload).encode()
        ),
    )

    result = PlaymatchResolver().identify(identity())

    assert result is not None
    assert not result.has_authoritative_content_match
    assert result.evidence[0].method == "FileNameAndSize"


def test_playmatch_can_identify_platform_when_local_platform_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "gameMatchType": "SHA1",
        "game": {
            "id": "11111111-1111-1111-1111-111111111111",
            "name": "Super Mario World (USA)",
        },
        "platform": {
            "id": "22222222-2222-2222-2222-222222222222",
            "name": "Super Nintendo Entertainment System",
        },
        "externalMetadata": [],
    }

    monkeypatch.setattr(
        "rom_metadata_framework.playmatch.urlopen",
        lambda request, timeout: FakeResponse(
            json.dumps(payload).encode()
        ),
    )

    unknown_platform_identity = RomIdentity(
        platform=None,
        format="sfc",
        file_name="meaningless.sfc",
        file_size=524288,
        hashes=HashSet(
            sha1="6b47bb75d16514b6a476aa0c73a683a2a4c18765",
        ),
    )

    result = PlaymatchResolver().identify(
        unknown_platform_identity
    )

    assert result is not None
    assert unknown_platform_identity.platform is None
    assert result.platform == "snes"
    assert result.evidence[0].method == "SHA1"
    assert result.evidence[0].authoritative
    assert (
        result.evidence[0].details["provider_platform"]
        == "Super Nintendo Entertainment System"
    )


def test_playmatch_preserves_catalogue_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "gameMatchType": "SHA1",
        "game": {
            "id": "11111111-1111-1111-1111-111111111111",
            "name": "Super Mario World (USA)",
        },
        "platform": {
            "id": "22222222-2222-2222-2222-222222222222",
            "name": "Super Nintendo Entertainment System",
        },
        "signatureGroup": {
            "id": "33333333-3333-3333-3333-333333333333",
            "name": "No-Intro",
        },
        "datFile": {
            "id": "44444444-4444-4444-4444-444444444444",
            "name": "Nintendo - Super Nintendo Entertainment System",
            "currentVersion": "20260614-014159",
        },
        "datFileImport": {
            "id": "55555555-5555-5555-5555-555555555555",
            "version": "20240821-143440",
        },
        "gameFiles": [
            {
                "id": "66666666-6666-6666-6666-666666666666",
                "fileName": "Super Mario World (USA).sfc",
                "fileSizeInBytes": 524288,
                "crc": "b19ed489",
                "md5": "cdd3c8c37322978ca8669b34bc89c804",
                "sha1": (
                    "6b47bb75d16514b6a476aa0c73a683"
                    "a2a4c18765"
                ),
                "sha256": (
                    "0838e531fe22c077528febe14cb3ff7"
                    "c492f1f5fa8de354192bdff7137c27f5b"
                ),
                "status": "Verified",
                "serial": None,
                "currentInLatestDat": True,
                "lastSeenDatVersion": "20260614-014159",
            }
        ],
        "externalMetadata": [],
    }

    monkeypatch.setattr(
        "rom_metadata_framework.playmatch.urlopen",
        lambda request, timeout: FakeResponse(
            json.dumps(payload).encode()
        ),
    )

    result = PlaymatchResolver().identify(identity())

    assert result is not None
    assert len(result.catalogue_evidence) == 1

    evidence = result.catalogue_evidence[0]

    assert evidence.authority == "No-Intro"
    assert (
        evidence.catalogue_name
        == "Nintendo - Super Nintendo Entertainment System"
    )
    assert evidence.catalogue_version == "20260614-014159"
    assert evidence.import_version == "20240821-143440"
    assert evidence.file_status == "verified"
    assert evidence.current_in_latest_catalogue is True
    assert evidence.match_method == "SHA1"
    assert evidence.is_strong_content_match


def test_playmatch_identify_lookup_accepts_normalized_hashes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from rom_metadata_framework.lookup import (
        LookupIdentity,
    )

    normalized_sha1 = (
        "a611b90b4833b20a364bf06ee3be3b9093ea4df9"
    )

    payload = {
        "gameMatchType": "SHA1",
        "game": {
            "id": "11111111-1111-1111-1111-111111111111",
            "name": "Super Mario Bros. 3 (USA)",
        },
        "platform": {
            "id": "22222222-2222-2222-2222-222222222222",
            "name": "Nintendo Entertainment System",
        },
        "externalMetadata": [],
    }

    def fake_urlopen(request, timeout):
        assert timeout == 10.0

        url = request.full_url

        assert "fileName=mutated.nes" in url
        assert "fileSize=393232" in url
        assert f"sha1={normalized_sha1}" in url

        return FakeResponse(
            json.dumps(payload).encode()
        )

    monkeypatch.setattr(
        "rom_metadata_framework.playmatch.urlopen",
        fake_urlopen,
    )

    lookup = LookupIdentity(
        file_name="mutated.nes",
        file_size=393232,
        hashes=HashSet(
            sha1=normalized_sha1,
        ),
    )

    result = PlaymatchResolver().identify_lookup(
        lookup
    )

    assert result is not None
    assert result.platform == "nes"
    assert (
        result.release_name
        == "Super Mario Bros. 3 (USA)"
    )
    assert result.evidence[0].method == "SHA1"
