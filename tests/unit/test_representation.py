import pytest

from rom_metadata_framework.representation import (
    RepresentationIdentity,
)


def test_representation_normalizes_names() -> None:
    representation = RepresentationIdentity(
        kind=" Disc-Image ",
        format=" RVZ ",
        metadata={
            "compression": "Zstandard",
        },
    )

    assert representation.kind == "disc-image"
    assert representation.format == "rvz"
    assert representation.metadata == {
        "compression": "Zstandard",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("kind", ""),
        ("format", "   "),
    ),
)
def test_representation_rejects_empty_names(
    field: str,
    value: str,
) -> None:
    kwargs = {
        "kind": "disc-image",
        "format": "rvz",
    }
    kwargs[field] = value

    with pytest.raises(ValueError):
        RepresentationIdentity(**kwargs)


def test_representation_metadata_is_immutable() -> None:
    representation = RepresentationIdentity(
        kind="disc-image",
        format="rvz",
        metadata={
            "compression": "Zstandard",
        },
    )

    with pytest.raises(TypeError):
        representation.metadata["compression"] = "none"


def test_nes_result_exposes_source_representation(
    tmp_path,
) -> None:
    from rom_metadata_framework.nes import NesAdapter

    payload = b"\x00" * (16 * 1024)

    header = bytearray(16)
    header[:4] = b"NES\x1a"
    header[4] = 1
    header[5] = 0

    path = tmp_path / "example.nes"
    path.write_bytes(bytes(header) + payload)

    result = NesAdapter().identify(path)

    representation = result.physical_representation

    assert representation is not None
    assert representation.kind == "cartridge-image"
    assert representation.format == "ines"

    # The normalized content remains independently described.
    assert result.content.kind == "cartridge"


def test_nes_identity_preserves_legacy_positional_arguments() -> None:
    from rom_metadata_framework.content import (
        NormalizedContentIdentity,
    )
    from rom_metadata_framework.nes import NesContentIdentity

    content = NormalizedContentIdentity(
        kind="cartridge",
    )

    result = NesContentIdentity(
        "ines",
        content,
        {"mapper": "1"},
    )

    assert result.header_metadata == {
        "mapper": "1",
    }
    assert result.physical_representation is not None
    assert result.physical_representation.format == "ines"


def test_dolphin_identity_preserves_legacy_positional_arguments() -> None:
    from rom_metadata_framework.content import (
        NormalizedContentIdentity,
    )
    from rom_metadata_framework.dolphin import (
        DolphinDiscIdentity,
    )

    content = NormalizedContentIdentity(
        kind="disc",
    )

    result = DolphinDiscIdentity(
        "gc",
        "rvz",
        "GALE01",
        2,
        content,
        "NTSC-U",
        "USA",
        "Super Smash Bros Melee",
        None,
        {
            "compression_method": "Zstandard",
        },
    )

    assert result.region == "NTSC-U"
    assert result.country == "USA"
    assert result.internal_name == "Super Smash Bros Melee"
    assert result.container_metadata == {
        "compression_method": "Zstandard",
    }

    representation = result.physical_representation

    assert representation is not None
    assert representation.kind == "disc-image"
    assert representation.format == "rvz"


def test_nes_representation_includes_header_metadata(
    tmp_path,
) -> None:
    from rom_metadata_framework.nes import NesAdapter

    payload = b"\x00" * (16 * 1024)

    header = bytearray(16)
    header[:4] = b"NES\x1a"
    header[4] = 1
    header[5] = 0
    header[6] = 0x10

    path = tmp_path / "mapper-test.nes"
    path.write_bytes(bytes(header) + payload)

    result = NesAdapter().identify(path)

    assert result.header_metadata["flags6"] == "10"
    assert (
        result.physical_representation.metadata["flags6"]
        == "10"
    )


def test_nes_representation_cannot_be_overridden() -> None:
    from rom_metadata_framework.content import (
        NormalizedContentIdentity,
    )
    from rom_metadata_framework.nes import NesContentIdentity

    with pytest.raises(TypeError):
        NesContentIdentity(
            representation="ines",
            content=NormalizedContentIdentity(
                kind="cartridge",
            ),
            physical_representation=RepresentationIdentity(
                kind="cartridge-image",
                format="headerless",
            ),
        )


def test_dolphin_representation_cannot_be_overridden() -> None:
    from rom_metadata_framework.content import (
        NormalizedContentIdentity,
    )
    from rom_metadata_framework.dolphin import (
        DolphinDiscIdentity,
    )

    with pytest.raises(TypeError):
        DolphinDiscIdentity(
            platform="gc",
            format="rvz",
            game_id="GALE01",
            revision=2,
            content=NormalizedContentIdentity(
                kind="disc",
            ),
            physical_representation=RepresentationIdentity(
                kind="disc-image",
                format="iso",
            ),
        )
