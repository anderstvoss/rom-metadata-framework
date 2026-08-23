import pytest

from rom_metadata_framework.identity import (
    AdapterProvenance,
    HashSet,
    RomIdentity,
)


def test_hashes_are_normalized_to_lowercase() -> None:
    hashes = HashSet(
        crc32="ABCDEF12",
        md5="ABCDEF0123456789ABCDEF0123456789",
        sha1="ABCDEF0123456789ABCDEF0123456789ABCDEF01",
    )

    assert hashes.crc32 == "abcdef12"
    assert hashes.md5 == "abcdef0123456789abcdef0123456789"
    assert hashes.sha1 == "abcdef0123456789abcdef0123456789abcdef01"


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("crc32", "1234"),
        ("md5", "not-a-valid-md5"),
        ("sha1", "g" * 40),
    ],
)
def test_invalid_hashes_are_rejected(field_name: str, value: str) -> None:
    kwargs = {field_name: value}

    with pytest.raises(ValueError):
        HashSet(**kwargs)


def test_identity_normalizes_optional_strings() -> None:
    identity = RomIdentity(
        platform="  gamecube  ",
        format=" rvz ",
        serial="  example-serial ",
    )

    assert identity.platform == "gamecube"
    assert identity.format == "rvz"
    assert identity.serial == "example-serial"


def test_media_metadata_is_immutable() -> None:
    identity = RomIdentity(
        media_metadata={
            "region": "USA",
        }
    )

    with pytest.raises(TypeError):
        identity.media_metadata["region"] = "EUR"


def test_adapter_provenance_is_normalized() -> None:
    adapter = AdapterProvenance(
        name="  generic-hash  ",
        version=" 0.1.0 ",
        backend=" python ",
    )

    assert adapter.name == "generic-hash"
    assert adapter.version == "0.1.0"
    assert adapter.backend == "python"


def test_specialized_identifiers_are_normalized() -> None:
    identity = RomIdentity(
        specialized_identifiers={
            "  RetroAchievements  ": "  Example-Identifier  ",
        }
    )

    assert (
        identity.specialized_identifiers["retroachievements"]
        == "Example-Identifier"
    )


def test_specialized_identifiers_are_immutable() -> None:
    identity = RomIdentity(
        specialized_identifiers={
            "retroachievements": "example",
        }
    )

    with pytest.raises(TypeError):
        identity.specialized_identifiers["retroachievements"] = "changed"


def test_specialized_identifier_rejects_empty_namespace() -> None:
    with pytest.raises(ValueError):
        RomIdentity(
            specialized_identifiers={
                "   ": "example",
            }
        )


def test_specialized_identifier_rejects_empty_value() -> None:
    with pytest.raises(ValueError):
        RomIdentity(
            specialized_identifiers={
                "retroachievements": "   ",
            }
        )


def test_specialized_identifier_rejects_normalized_duplicate_namespace() -> None:
    with pytest.raises(ValueError):
        RomIdentity(
            specialized_identifiers={
                "RetroAchievements": "first",
                " retroachievements ": "second",
            }
        )


def test_generic_md5_and_specialized_identifier_remain_distinct() -> None:
    value = "cdd3c8c37322978ca8669b34bc89c804"

    identity = RomIdentity(
        hashes=HashSet(md5=value),
        specialized_identifiers={
            "retroachievements": value,
        },
    )

    assert identity.hashes.md5 == value
    assert identity.specialized_identifiers["retroachievements"] == value
