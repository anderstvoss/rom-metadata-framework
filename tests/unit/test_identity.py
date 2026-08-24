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
        sha256=(
            "ABCDEF0123456789ABCDEF0123456789"
            "ABCDEF0123456789ABCDEF0123456789"
        ),
    )

    assert hashes.crc32 == "abcdef12"
    assert hashes.md5 == "abcdef0123456789abcdef0123456789"
    assert hashes.sha1 == "abcdef0123456789abcdef0123456789abcdef01"
    assert hashes.sha256 == (
        "abcdef0123456789abcdef0123456789"
        "abcdef0123456789abcdef0123456789"
    )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("crc32", "1234"),
        ("md5", "not-a-valid-md5"),
        ("sha1", "g" * 40),
        ("sha256", "f" * 63),
        ("sha256", "g" * 64),
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

    assert identity.platform == "gc"
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


def test_identity_normalizes_source_file_metadata() -> None:
    identity = RomIdentity(
        file_name="  game.sfc  ",
        file_size=1234,
    )

    assert identity.file_name == "game.sfc"
    assert identity.file_size == 1234


def test_identity_rejects_negative_file_size() -> None:
    with pytest.raises(ValueError):
        RomIdentity(file_size=-1)


def test_identity_rejects_non_integer_file_size() -> None:
    with pytest.raises(TypeError):
        RomIdentity(file_size="123")  # type: ignore[arg-type]


def test_generic_hasher_includes_sha256(tmp_path) -> None:
    import hashlib

    from rom_metadata_framework.hashing import hash_file

    payload = b"rom-metadata-framework sha256 test\n"
    path = tmp_path / "sample.bin"
    path.write_bytes(payload)

    hashes = hash_file(path)

    assert hashes.sha256 == hashlib.sha256(payload).hexdigest()


def test_identity_canonicalizes_platform_aliases() -> None:
    from rom_metadata_framework.identity import (
        RomIdentity,
    )

    cases = {
        "gamecube": "gc",
        "nintendo-gamecube": "gc",
        "playstation-2": "ps2",
        "sony-playstation-3": "ps3",
        "xbox-360": "xbox360",
        "nintendo-switch": "switch",
        "game-boy-advance": "gba",
    }

    for supplied, expected in cases.items():
        identity = RomIdentity(
            platform=supplied,
        )

        assert identity.platform == expected


def test_identity_preserves_unknown_platform_value() -> None:
    from rom_metadata_framework.identity import (
        RomIdentity,
    )

    identity = RomIdentity(
        platform="future-console",
    )

    assert identity.platform == "future-console"
