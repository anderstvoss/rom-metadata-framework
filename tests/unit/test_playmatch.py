import json
from io import BytesIO
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

    def __enter__(self) -> "FakeResponse":
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
