from pathlib import Path

import pytest

from rom_metadata_framework.xbox360 import (
    Xbox360FormatError,
    Xbox360PlatformDetector,
    Xbox360StructuralInspector,
    inspect_xbox360_disc,
)
from rom_metadata_framework.xdvdfs import (
    XDVDFS_MAGIC,
    XDVDFS_SECTOR_SIZE,
)

SECTOR = XDVDFS_SECTOR_SIZE


def _directory_node(
    *,
    name: str,
    sector: int,
    size: int,
    attributes: int = 0x80,
) -> bytes:
    encoded = name.encode("ascii")
    data = bytearray(
        14 + len(encoded)
    )

    data[4:8] = sector.to_bytes(
        4,
        "little",
    )
    data[8:12] = size.to_bytes(
        4,
        "little",
    )
    data[12] = attributes
    data[13] = len(encoded)
    data[14:] = encoded

    while len(data) % 4:
        data.append(0xFF)

    return bytes(data)


def _make_xex(
    *,
    title_id: int = 0x12345678,
    media_id: int = 0xA1B2C3D4,
    version: int = 8,
    base_version: int = 7,
    disc_number: int = 1,
    disc_count: int = 1,
) -> bytes:
    execution_offset = 0x80

    data = bytearray(0x100)

    data[:4] = b"XEX2"

    data[0x14:0x18] = (
        (1).to_bytes(
            4,
            "big",
        )
    )

    data[0x18:0x1C] = (
        0x00040006
    ).to_bytes(
        4,
        "big",
    )

    data[0x1C:0x20] = (
        execution_offset
    ).to_bytes(
        4,
        "big",
    )

    execution = bytearray(20)

    execution[0:4] = media_id.to_bytes(
        4,
        "big",
    )
    execution[4:8] = version.to_bytes(
        4,
        "big",
    )
    execution[8:12] = (
        base_version.to_bytes(
            4,
            "big",
        )
    )
    execution[12:16] = (
        title_id.to_bytes(
            4,
            "big",
        )
    )
    execution[16] = 0
    execution[17] = 0
    execution[18] = disc_number
    execution[19] = disc_count

    data[
        execution_offset:
        execution_offset + 20
    ] = execution

    return bytes(data)


def _write_disc(
    path: Path,
    *,
    xex: bytes | None = None,
    name: str = "default.xex",
) -> None:
    partition = 0x0000FB20
    descriptor_offset = (
        partition + 32 * SECTOR
    )

    root_sector = 40
    xex_sector = 41

    if xex is None:
        xex = _make_xex()

    root = _directory_node(
        name=name,
        sector=xex_sector,
        size=len(xex),
    )

    root_data = root.ljust(
        SECTOR,
        b"\x00",
    )

    total_size = (
        partition
        + xex_sector * SECTOR
        + len(xex)
    )

    image = bytearray(total_size)

    descriptor = bytearray(SECTOR)
    descriptor[:20] = XDVDFS_MAGIC
    descriptor[0x7EC:0x800] = XDVDFS_MAGIC

    descriptor[0x14:0x18] = (
        root_sector.to_bytes(
            4,
            "little",
        )
    )
    descriptor[0x18:0x1C] = (
        SECTOR.to_bytes(
            4,
            "little",
        )
    )

    image[
        descriptor_offset:
        descriptor_offset + SECTOR
    ] = descriptor

    root_offset = (
        partition
        + root_sector * SECTOR
    )

    image[
        root_offset:
        root_offset + SECTOR
    ] = root_data

    xex_offset = (
        partition
        + xex_sector * SECTOR
    )

    image[
        xex_offset:
        xex_offset + len(xex)
    ] = xex

    path.write_bytes(image)


def test_inspects_xbox360_execution_id(
    tmp_path: Path,
) -> None:
    path = tmp_path / "disc.iso"
    _write_disc(path)

    metadata = inspect_xbox360_disc(
        path
    )

    execution = metadata.execution_id

    assert execution.title_id == "12345678"
    assert execution.media_id == "A1B2C3D4"
    assert execution.version == 8
    assert execution.base_version == 7
    assert execution.disc_number == 1
    assert execution.disc_count == 1


def test_detector_identifies_xbox360(
    tmp_path: Path,
) -> None:
    path = tmp_path / "candidate.bin"
    _write_disc(path)

    detection = (
        Xbox360PlatformDetector()
        .detect(path)
    )

    assert detection.best is not None
    assert (
        detection.best.platform
        == "xbox-360"
    )

    evidence = detection.best.evidence[0]

    assert (
        evidence.method
        == "xdvdfs-xex2-execution-id"
    )


def test_inspector_preserves_local_metadata(
    tmp_path: Path,
) -> None:
    path = tmp_path / "disc.iso"
    _write_disc(path)

    result = (
        Xbox360StructuralInspector()
        .inspect(path)
    )

    assert result is not None

    assert (
        result.physical_representation.format
        == "xbox360-xgd"
    )

    metadata = result.local_metadata

    assert metadata.platform == "xbox-360"

    identifiers = {
        item.namespace: item.value
        for item in metadata.identifiers
    }

    assert (
        identifiers["xbox360-title-id"]
        == "12345678"
    )
    assert (
        identifiers["xbox360-media-id"]
        == "A1B2C3D4"
    )

    assert (
        metadata.boot["executable"]
        == "default.xex"
    )


def test_rejects_missing_default_xex(
    tmp_path: Path,
) -> None:
    path = tmp_path / "disc.iso"

    _write_disc(
        path,
        name="something.bin",
    )

    with pytest.raises(
        Xbox360FormatError,
        match="default.xex",
    ):
        inspect_xbox360_disc(path)


def test_rejects_non_xex2_default_executable(
    tmp_path: Path,
) -> None:
    path = tmp_path / "disc.iso"

    xex = bytearray(
        _make_xex()
    )
    xex[:4] = b"NOPE"

    _write_disc(
        path,
        xex=bytes(xex),
    )

    with pytest.raises(
        Xbox360FormatError,
        match="XEX2 magic",
    ):
        inspect_xbox360_disc(path)


def test_rejects_missing_execution_id(
    tmp_path: Path,
) -> None:
    path = tmp_path / "disc.iso"

    xex = bytearray(
        _make_xex()
    )

    xex[0x18:0x1C] = (
        0x00010100
    ).to_bytes(
        4,
        "big",
    )

    _write_disc(
        path,
        xex=bytes(xex),
    )

    with pytest.raises(
        Xbox360FormatError,
        match="Execution ID header is missing",
    ):
        inspect_xbox360_disc(path)


def test_rejects_invalid_disc_numbers(
    tmp_path: Path,
) -> None:
    path = tmp_path / "disc.iso"

    _write_disc(
        path,
        xex=_make_xex(
            disc_number=2,
            disc_count=1,
        ),
    )

    with pytest.raises(
        Xbox360FormatError,
        match="exceeds disc count",
    ):
        inspect_xbox360_disc(path)


def test_rejects_excessive_optional_header_count(
    tmp_path: Path,
) -> None:
    path = tmp_path / "disc.iso"

    xex = bytearray(
        _make_xex()
    )

    xex[0x14:0x18] = (
        4097
    ).to_bytes(
        4,
        "big",
    )

    _write_disc(
        path,
        xex=bytes(xex),
    )

    with pytest.raises(
        Xbox360FormatError,
        match="optional header count exceeds",
    ):
        inspect_xbox360_disc(path)


def test_rejects_execution_id_beyond_xex(
    tmp_path: Path,
) -> None:
    path = tmp_path / "disc.iso"

    xex = bytearray(
        _make_xex()
    )

    xex[0x1C:0x20] = (
        0x1000
    ).to_bytes(
        4,
        "big",
    )

    _write_disc(
        path,
        xex=bytes(xex),
    )

    with pytest.raises(
        Xbox360FormatError,
        match="range",
    ):
        inspect_xbox360_disc(path)


def test_rejects_zero_disc_count(
    tmp_path: Path,
) -> None:
    path = tmp_path / "disc.iso"

    _write_disc(
        path,
        xex=_make_xex(
            disc_number=1,
            disc_count=0,
        ),
    )

    with pytest.raises(
        Xbox360FormatError,
        match="disc count is invalid",
    ):
        inspect_xbox360_disc(path)


def test_rejects_zero_disc_number(
    tmp_path: Path,
) -> None:
    path = tmp_path / "disc.iso"

    _write_disc(
        path,
        xex=_make_xex(
            disc_number=0,
            disc_count=1,
        ),
    )

    with pytest.raises(
        Xbox360FormatError,
        match="disc number is invalid",
    ):
        inspect_xbox360_disc(path)


def test_rejects_duplicate_execution_id_headers(
    tmp_path: Path,
) -> None:
    path = tmp_path / "disc.iso"

    xex = bytearray(
        _make_xex()
    )

    xex[0x14:0x18] = (
        2
    ).to_bytes(
        4,
        "big",
    )

    xex[0x20:0x24] = (
        0x00040006
    ).to_bytes(
        4,
        "big",
    )

    xex[0x24:0x28] = (
        0x80
    ).to_bytes(
        4,
        "big",
    )

    _write_disc(
        path,
        xex=bytes(xex),
    )

    with pytest.raises(
        Xbox360FormatError,
        match="duplicate Execution ID",
    ):
        inspect_xbox360_disc(path)
