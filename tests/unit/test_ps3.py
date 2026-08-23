from __future__ import annotations

import struct
from pathlib import Path

from rom_metadata_framework.ps3 import (
    Ps3PlatformDetector,
    Ps3StructuralInspector,
    inspect_ps3_iso,
)

SECTOR = 2048


def _both_u16(value: int) -> bytes:
    return (
        value.to_bytes(2, "little")
        + value.to_bytes(2, "big")
    )


def _both_u32(value: int) -> bytes:
    return (
        value.to_bytes(4, "little")
        + value.to_bytes(4, "big")
    )


def _directory_record(
    name: bytes,
    *,
    extent: int,
    size: int,
    directory: bool,
) -> bytes:
    length = 33 + len(name)

    if length % 2:
        length += 1

    record = bytearray(length)
    record[0] = length
    record[2:10] = _both_u32(extent)
    record[10:18] = _both_u32(size)
    record[25] = 0x02 if directory else 0
    record[28:32] = _both_u16(1)
    record[32] = len(name)
    record[33 : 33 + len(name)] = name

    return bytes(record)


def _directory(entries: tuple[bytes, ...]) -> bytes:
    data = bytearray(SECTOR)
    offset = 0

    for entry in entries:
        data[
            offset : offset + len(entry)
        ] = entry
        offset += len(entry)

    return bytes(data)


def _make_sfb(
    title_id: str = "BLUS12345",
) -> bytes:
    data = bytearray(0x600)
    data[:8] = b".SFB\x00\x01\x00\x00"

    key = b"TITLE_ID"
    record = 0x20

    data[
        record : record + len(key)
    ] = key

    value_offset = 0x220
    value_size = 0x10

    data[
        record + 16 : record + 20
    ] = value_offset.to_bytes(4, "big")

    data[
        record + 20 : record + 24
    ] = value_size.to_bytes(4, "big")

    formatted = (
        title_id[:4]
        + "-"
        + title_id[4:]
    ).encode("ascii")

    data[
        value_offset : value_offset + len(formatted)
    ] = formatted

    return bytes(data)


def _make_sfo(
    *,
    title_id: str = "BLUS12345",
    category: str = "DG",
) -> bytes:
    values: tuple[
        tuple[str, int, str | int],
        ...
    ] = (
        ("APP_VER", 0x0204, "01.00"),
        ("BOOTABLE", 0x0404, 1),
        ("CATEGORY", 0x0204, category),
        ("PS3_SYSTEM_VER", 0x0204, "04.2500"),
        ("TITLE", 0x0204, "Synthetic PS3 Game"),
        ("TITLE_ID", 0x0204, title_id),
        ("VERSION", 0x0204, "01.00"),
    )

    key_table = bytearray()
    value_table = bytearray()
    index_records = []

    for key, fmt, value in values:
        key_offset = len(key_table)
        key_table += key.encode("utf-8") + b"\x00"

        while len(value_table) % 4:
            value_table += b"\x00"

        value_offset = len(value_table)

        if fmt == 0x0204:
            raw = str(value).encode("utf-8") + b"\x00"
            maximum = len(raw)
        else:
            raw = int(value).to_bytes(4, "little")
            maximum = 4

        value_table += raw

        index_records.append(
            (
                key_offset,
                fmt,
                len(raw),
                maximum,
                value_offset,
            )
        )

    keys_offset = 20 + len(index_records) * 16
    values_offset = keys_offset + len(key_table)

    header = (
        b"\x00PSF"
        + struct.pack(
            "<4I",
            0x00000101,
            keys_offset,
            values_offset,
            len(index_records),
        )
    )

    index = b"".join(
        struct.pack(
            "<HHIII",
            *record,
        )
        for record in index_records
    )

    return (
        header
        + index
        + bytes(key_table)
        + bytes(value_table)
    )


def _write_ps3_iso(
    path: Path,
    *,
    sfo_title_id: str = "BLUS12345",
    sfb_title_id: str = "BLUS12345",
    category: str = "DG",
    include_sfb: bool = True,
) -> None:
    root_extent = 32
    ps3_game_extent = 33
    usrdir_extent = 34
    sfb_extent = 40
    sfo_extent = 41
    eboot_extent = 42

    sfb = _make_sfb(sfb_title_id)
    sfo = _make_sfo(
        title_id=sfo_title_id,
        category=category,
    )

    root_entries = [
        _directory_record(
            b"\x00",
            extent=root_extent,
            size=SECTOR,
            directory=True,
        ),
        _directory_record(
            b"\x01",
            extent=root_extent,
            size=SECTOR,
            directory=True,
        ),
        _directory_record(
            b"PS3_GAME",
            extent=ps3_game_extent,
            size=SECTOR,
            directory=True,
        ),
    ]

    if include_sfb:
        root_entries.append(
            _directory_record(
                b"PS3_DISC.SFB;1",
                extent=sfb_extent,
                size=len(sfb),
                directory=False,
            )
        )

    ps3_game = _directory(
        (
            _directory_record(
                b"\x00",
                extent=ps3_game_extent,
                size=SECTOR,
                directory=True,
            ),
            _directory_record(
                b"\x01",
                extent=root_extent,
                size=SECTOR,
                directory=True,
            ),
            _directory_record(
                b"PARAM.SFO;1",
                extent=sfo_extent,
                size=len(sfo),
                directory=False,
            ),
            _directory_record(
                b"USRDIR",
                extent=usrdir_extent,
                size=SECTOR,
                directory=True,
            ),
        )
    )

    usrdir = _directory(
        (
            _directory_record(
                b"\x00",
                extent=usrdir_extent,
                size=SECTOR,
                directory=True,
            ),
            _directory_record(
                b"\x01",
                extent=ps3_game_extent,
                size=SECTOR,
                directory=True,
            ),
            _directory_record(
                b"EBOOT.BIN;1",
                extent=eboot_extent,
                size=16,
                directory=False,
            ),
        )
    )

    pvd = bytearray(SECTOR)
    pvd[0] = 1
    pvd[1:6] = b"CD001"
    pvd[6] = 1
    pvd[40:49] = b"PS3VOLUME"
    pvd[128:132] = _both_u16(SECTOR)

    root_record = _directory_record(
        b"\x00",
        extent=root_extent,
        size=SECTOR,
        directory=True,
    )

    pvd[
        156 : 156 + len(root_record)
    ] = root_record

    size = (eboot_extent + 1) * SECTOR
    image = bytearray(size)

    image[
        16 * SECTOR : 17 * SECTOR
    ] = pvd

    image[
        root_extent * SECTOR
        : (root_extent + 1) * SECTOR
    ] = _directory(tuple(root_entries))

    image[
        ps3_game_extent * SECTOR
        : (ps3_game_extent + 1) * SECTOR
    ] = ps3_game

    image[
        usrdir_extent * SECTOR
        : (usrdir_extent + 1) * SECTOR
    ] = usrdir

    if include_sfb:
        start = sfb_extent * SECTOR
        image[start : start + len(sfb)] = sfb

    start = sfo_extent * SECTOR
    image[start : start + len(sfo)] = sfo

    image[
        eboot_extent * SECTOR
        : eboot_extent * SECTOR + 16
    ] = b"synthetic-eboot!"

    path.write_bytes(image)


def test_inspect_ps3_iso_extracts_disc_metadata(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"
    _write_ps3_iso(path)

    metadata = inspect_ps3_iso(path)

    assert metadata.volume_identifier == "PS3VOLUME"
    assert metadata.title_id == "BLUS12345"
    assert metadata.sfb_title_id == "BLUS12345"
    assert metadata.category == "DG"
    assert metadata.title == "Synthetic PS3 Game"
    assert metadata.app_version == "01.00"
    assert metadata.version == "01.00"
    assert metadata.system_version == "04.2500"
    assert metadata.bootable == 1
    assert metadata.eboot_present


def test_ps3_detector_uses_sfb_and_sfo_evidence(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"
    _write_ps3_iso(path)

    detection = Ps3PlatformDetector().detect(path)

    assert detection.best is not None
    assert detection.best.platform == "playstation-3"
    assert detection.best.confidence == 100

    evidence = detection.best.evidence[0]

    assert evidence.source == "ps3-disc-structure"
    assert evidence.method == "sfb-param-sfo"
    assert evidence.value == "BLUS12345"
    assert evidence.details["category"] == "DG"


def test_ps3_inspector_returns_representation_and_local_metadata(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"
    _write_ps3_iso(path)

    result = Ps3StructuralInspector().inspect(path)

    assert result is not None
    assert result.physical_representation is not None
    assert result.physical_representation.kind == "disc-image"
    assert result.physical_representation.format == "iso9660"

    local = result.local_metadata

    assert local is not None
    assert local.platform == "playstation-3"
    assert local.identifiers[0].namespace == "ps3-title-id"
    assert local.identifiers[0].value == "BLUS12345"
    assert local.titles[0].value == "Synthetic PS3 Game"
    assert local.software_versions[0].value == "01.00"


def test_ps3_rejects_non_disc_category(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"

    _write_ps3_iso(
        path,
        category="HG",
    )

    assert Ps3PlatformDetector().detect(path).best is None
    assert Ps3StructuralInspector().inspect(path) is None


def test_ps3_rejects_mismatched_title_ids(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"

    _write_ps3_iso(
        path,
        sfo_title_id="BLUS12345",
        sfb_title_id="BLUS99999",
    )

    assert Ps3PlatformDetector().detect(path).best is None


def test_ps3_rejects_disc_without_sfb(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"

    _write_ps3_iso(
        path,
        include_sfb=False,
    )

    assert Ps3PlatformDetector().detect(path).best is None


def test_ps3_rejects_non_iso(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ordinary.bin"
    path.write_bytes(b"ordinary")

    assert Ps3PlatformDetector().detect(path).best is None


def test_ps3_rejects_invalid_sfb_magic(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"
    _write_ps3_iso(path)

    image = bytearray(path.read_bytes())

    sfb_offset = 40 * SECTOR
    image[
        sfb_offset : sfb_offset + 4
    ] = b"BAD!"

    path.write_bytes(image)

    assert Ps3PlatformDetector().detect(path).best is None
    assert Ps3StructuralInspector().inspect(path) is None


def test_ps3_rejects_invalid_sfo_magic(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"
    _write_ps3_iso(path)

    image = bytearray(path.read_bytes())

    sfo_offset = 41 * SECTOR
    image[
        sfo_offset : sfo_offset + 4
    ] = b"BAD!"

    path.write_bytes(image)

    assert Ps3PlatformDetector().detect(path).best is None
    assert Ps3StructuralInspector().inspect(path) is None


def test_ps3_rejects_sfo_used_length_over_maximum(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"
    _write_ps3_iso(path)

    image = bytearray(path.read_bytes())

    # First PARAM.SFO index entry begins at +20.
    # used_length is at offset +4 within the 16-byte entry.
    used_length_offset = (
        41 * SECTOR
        + 20
        + 4
    )

    image[
        used_length_offset :
        used_length_offset + 4
    ] = (16).to_bytes(4, "little")

    path.write_bytes(image)

    assert Ps3PlatformDetector().detect(path).best is None


def test_ps3_rejects_sfo_value_beyond_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"
    _write_ps3_iso(path)

    image = bytearray(path.read_bytes())

    # First PARAM.SFO entry data offset is at +12
    # within the entry. Push it beyond the metadata file.
    value_offset_location = (
        41 * SECTOR
        + 20
        + 12
    )

    image[
        value_offset_location :
        value_offset_location + 4
    ] = (0xFFFFFF00).to_bytes(
        4,
        "little",
    )

    path.write_bytes(image)

    assert Ps3PlatformDetector().detect(path).best is None


def test_ps3_rejects_invalid_title_id_shape(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"

    _write_ps3_iso(
        path,
        sfo_title_id="INVALID01",
        sfb_title_id="INVALID01",
    )

    assert Ps3PlatformDetector().detect(path).best is None


def test_ps3_rejects_non_ascii_sfb_key(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"
    _write_ps3_iso(path)

    image = bytearray(path.read_bytes())

    # First SFB record begins at +0x20.
    image[
        40 * SECTOR + 0x20
    ] = 0xFF

    path.write_bytes(image)

    assert Ps3PlatformDetector().detect(path).best is None
    assert Ps3StructuralInspector().inspect(path) is None


def test_ps3_rejects_non_ascii_sfb_title_id(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"
    _write_ps3_iso(path)

    image = bytearray(path.read_bytes())

    # Synthetic SFB TITLE_ID payload begins at +0x220.
    image[
        40 * SECTOR + 0x220
    ] = 0xFF

    path.write_bytes(image)

    assert Ps3PlatformDetector().detect(path).best is None
    assert Ps3StructuralInspector().inspect(path) is None


def test_ps3_rejects_duplicate_sfo_keys(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"
    _write_ps3_iso(path)

    image = bytearray(path.read_bytes())

    sfo_offset = 41 * SECTOR

    # PARAM.SFO index entry 0 begins at +20.
    # Entry 1 begins at +36. Make entry 1's key-relative
    # offset equal zero so it aliases entry 0's APP_VER key.
    second_key_relative = (
        sfo_offset
        + 20
        + 16
    )

    image[
        second_key_relative :
        second_key_relative + 2
    ] = (0).to_bytes(2, "little")

    path.write_bytes(image)

    assert Ps3PlatformDetector().detect(path).best is None
    assert Ps3StructuralInspector().inspect(path) is None
