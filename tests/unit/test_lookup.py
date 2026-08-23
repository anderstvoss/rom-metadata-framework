import pytest

from rom_metadata_framework.identity import (
    HashSet,
    RomIdentity,
)
from rom_metadata_framework.lookup import (
    LookupIdentity,
)


def test_lookup_identity_from_rom_identity() -> None:
    rom = RomIdentity(
        file_name="example.rom",
        file_size=1234,
        hashes=HashSet(
            sha1=(
                "0123456789abcdef0123456789abcdef"
                "01234567"
            ),
        ),
    )

    lookup = LookupIdentity.from_rom_identity(
        rom
    )

    assert lookup.file_name == "example.rom"
    assert lookup.file_size == 1234
    assert lookup.hashes is rom.hashes


def test_lookup_identity_can_use_independent_hashes() -> None:
    physical = HashSet(
        sha1=(
            "0123456789abcdef0123456789abcdef"
            "01234567"
        ),
    )

    normalized = HashSet(
        sha1=(
            "89abcdef0123456789abcdef01234567"
            "89abcdef"
        ),
    )

    rom = RomIdentity(
        file_name="example.nes",
        file_size=100,
        hashes=physical,
    )

    lookup = LookupIdentity(
        file_name=rom.file_name or "",
        file_size=rom.file_size or 0,
        hashes=normalized,
    )

    assert rom.hashes is physical
    assert lookup.hashes is normalized
    assert lookup.hashes != rom.hashes


def test_lookup_identity_requires_file_name() -> None:
    with pytest.raises(ValueError):
        LookupIdentity(
            file_name=" ",
            file_size=1,
        )


def test_lookup_identity_rejects_negative_size() -> None:
    with pytest.raises(ValueError):
        LookupIdentity(
            file_name="example.rom",
            file_size=-1,
        )


def test_lookup_from_rom_requires_source_metadata() -> None:
    with pytest.raises(ValueError):
        LookupIdentity.from_rom_identity(
            RomIdentity(
                hashes=HashSet(
                    crc32="12345678",
                ),
            )
        )
