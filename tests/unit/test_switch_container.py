from pathlib import Path

import pytest

from rom_metadata_framework.switch_container import (
    HFS0_MAGIC,
    PFS0_MAGIC,
    SwitchContainerError,
    find_entry,
    parse_hfs0,
    parse_pfs0,
    parse_xci,
    read_entry_range,
)


def _pfs0(
    entries: tuple[
        tuple[str, bytes],
        ...,
    ],
) -> bytes:
    strings = bytearray()
    records = bytearray()
    payload = bytearray()

    for name, data in entries:
        name_offset = len(strings)

        strings.extend(
            name.encode("utf-8")
            + b"\x00"
        )

        records.extend(
            len(payload).to_bytes(
                8,
                "little",
            )
        )
        records.extend(
            len(data).to_bytes(
                8,
                "little",
            )
        )
        records.extend(
            name_offset.to_bytes(
                4,
                "little",
            )
        )
        records.extend(
            bytes(4)
        )

        payload.extend(data)

    header = (
        PFS0_MAGIC
        + len(entries).to_bytes(
            4,
            "little",
        )
        + len(strings).to_bytes(
            4,
            "little",
        )
        + bytes(4)
    )

    return bytes(
        header
        + records
        + strings
        + payload
    )


def _hfs0(
    entries: tuple[
        tuple[str, bytes],
        ...,
    ],
) -> bytes:
    strings = bytearray()
    records = bytearray()
    payload = bytearray()

    for name, data in entries:
        name_offset = len(strings)

        strings.extend(
            name.encode("utf-8")
            + b"\x00"
        )

        records.extend(
            len(payload).to_bytes(
                8,
                "little",
            )
        )
        records.extend(
            len(data).to_bytes(
                8,
                "little",
            )
        )
        records.extend(
            name_offset.to_bytes(
                4,
                "little",
            )
        )
        records.extend(
            len(data).to_bytes(
                4,
                "little",
            )
        )
        records.extend(
            bytes(8)
        )
        records.extend(
            bytes.fromhex(
                "11" * 32
            )
        )

        payload.extend(data)

    header = (
        HFS0_MAGIC
        + len(entries).to_bytes(
            4,
            "little",
        )
        + len(strings).to_bytes(
            4,
            "little",
        )
        + bytes(4)
    )

    return bytes(
        header
        + records
        + strings
        + payload
    )


def _write_xci(
    path: Path,
) -> None:
    secure = _hfs0(
        (
            (
                "00112233445566778899aabbccddeeff.nca",
                b"encrypted-nca",
            ),
            (
                "11223344556677889900aabbccddeeff.cnmt.nca",
                b"encrypted-cnmt",
            ),
        )
    )

    root = _hfs0(
        (
            (
                "secure",
                secure,
            ),
        )
    )

    root_offset = 0x200

    header = bytearray(
        root_offset
    )

    header[
        0x100:0x104
    ] = b"HEAD"

    header[
        0x130:0x138
    ] = root_offset.to_bytes(
        8,
        "little",
    )

    path.write_bytes(
        bytes(header)
        + root
    )


def test_parse_pfs0_reads_entries(
    tmp_path: Path,
) -> None:
    path = tmp_path / "package.nsp"

    path.write_bytes(
        _pfs0(
            (
                (
                    "00112233445566778899aabbccddeeff.nca",
                    b"NCA0",
                ),
                (
                    "11223344556677889900aabbccddeeff.cnmt.nca",
                    b"META",
                ),
            )
        )
    )

    table = parse_pfs0(path)

    assert table.format == "pfs0"
    assert len(table.entries) == 2

    entry = find_entry(
        table,
        "00112233445566778899AABBCCDDEEFF.NCA",
    )

    assert entry is not None
    assert entry.size == 4

    assert (
        read_entry_range(
            path,
            entry,
            offset=0,
            size=4,
            max_size=4,
        )
        == b"NCA0"
    )


def test_parse_hfs0_reads_entry_metadata(
    tmp_path: Path,
) -> None:
    path = tmp_path / "partition.bin"

    path.write_bytes(
        _hfs0(
            (
                (
                    "secure.bin",
                    b"payload",
                ),
            )
        )
    )

    table = parse_hfs0(
        path,
        offset=0,
    )

    assert table.format == "hfs0"
    assert len(table.entries) == 1

    entry = table.entries[0]

    assert entry.name == "secure.bin"
    assert entry.size == 7
    assert entry.hashed_size == 7
    assert entry.hash_hex == (
        "11" * 32
    )


def test_parse_xci_reads_secure_partition(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.xci"
    _write_xci(path)

    structure = parse_xci(path)

    assert (
        structure.root_hfs0_offset
        == 0x200
    )

    assert [
        entry.name
        for entry
        in structure.root.entries
    ] == [
        "secure",
    ]

    assert len(
        structure.secure.entries
    ) == 2


def test_pfs0_rejects_wrong_magic(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bad.nsp"
    path.write_bytes(
        b"BAD!"
        + bytes(64)
    )

    with pytest.raises(
        SwitchContainerError,
        match="PFS0 magic",
    ):
        parse_pfs0(path)


def test_hfs0_rejects_wrong_magic(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bad.bin"
    path.write_bytes(
        b"BAD!"
        + bytes(64)
    )

    with pytest.raises(
        SwitchContainerError,
        match="HFS0 magic",
    ):
        parse_hfs0(
            path,
            offset=0,
        )


def test_xci_rejects_missing_head(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bad.xci"
    path.write_bytes(
        bytes(0x400)
    )

    with pytest.raises(
        SwitchContainerError,
        match="HEAD",
    ):
        parse_xci(path)


def test_xci_rejects_invalid_root_offset(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bad.xci"

    data = bytearray(
        0x400
    )
    data[
        0x100:0x104
    ] = b"HEAD"
    data[
        0x130:0x138
    ] = (
        0x201
    ).to_bytes(
        8,
        "little",
    )

    path.write_bytes(data)

    with pytest.raises(
        SwitchContainerError,
        match="root HFS0 offset",
    ):
        parse_xci(path)


def test_xci_rejects_missing_secure_partition(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bad.xci"

    root = _hfs0(
        (
            (
                "normal",
                b"",
            ),
        )
    )

    header = bytearray(
        0x200
    )
    header[
        0x100:0x104
    ] = b"HEAD"
    header[
        0x130:0x138
    ] = (
        0x200
    ).to_bytes(
        8,
        "little",
    )

    path.write_bytes(
        bytes(header)
        + root
    )

    with pytest.raises(
        SwitchContainerError,
        match="secure partition",
    ):
        parse_xci(path)


def test_pfs0_rejects_extent_beyond_source(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bad.nsp"

    data = bytearray(
        _pfs0(
            (
                (
                    "entry.nca",
                    b"four",
                ),
            )
        )
    )

    data[
        0x18:0x20
    ] = (
        0x100000
    ).to_bytes(
        8,
        "little",
    )

    path.write_bytes(data)

    with pytest.raises(
        SwitchContainerError,
        match="extends beyond",
    ):
        parse_pfs0(path)


def test_hfs0_rejects_hashed_size_beyond_entry(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bad.bin"

    data = bytearray(
        _hfs0(
            (
                (
                    "entry.nca",
                    b"four",
                ),
            )
        )
    )

    data[
        0x24:0x28
    ] = (
        5
    ).to_bytes(
        4,
        "little",
    )

    path.write_bytes(data)

    with pytest.raises(
        SwitchContainerError,
        match="hashed size",
    ):
        parse_hfs0(
            path,
            offset=0,
        )


def test_read_entry_range_enforces_bound(
    tmp_path: Path,
) -> None:
    path = tmp_path / "package.nsp"

    path.write_bytes(
        _pfs0(
            (
                (
                    "entry.nca",
                    b"12345678",
                ),
            )
        )
    )

    entry = parse_pfs0(
        path
    ).entries[0]

    with pytest.raises(
        SwitchContainerError,
        match="bounded read limit",
    ):
        read_entry_range(
            path,
            entry,
            offset=0,
            size=8,
            max_size=4,
        )


def test_missing_source_is_rejected(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        SwitchContainerError,
        match="not a regular file",
    ):
        parse_pfs0(
            tmp_path / "missing.nsp"
        )


def test_pfs0_rejects_file_count_over_bound(
    tmp_path: Path,
) -> None:
    path = tmp_path / "package.nsp"
    path.write_bytes(
        b"PFS0"
        + (2).to_bytes(4, "little")
        + bytes(8)
        + bytes(64)
    )

    with pytest.raises(
        SwitchContainerError,
        match="file count exceeds",
    ):
        parse_pfs0(
            path,
            max_files=1,
        )


def test_pfs0_rejects_string_table_over_bound(
    tmp_path: Path,
) -> None:
    path = tmp_path / "package.nsp"
    path.write_bytes(
        b"PFS0"
        + bytes(4)
        + (2).to_bytes(4, "little")
        + bytes(4)
        + b"\x00\x00"
    )

    with pytest.raises(
        SwitchContainerError,
        match="string table exceeds",
    ):
        parse_pfs0(
            path,
            max_string_table_size=1,
        )


def test_read_entry_range_rejects_negative_offset(
    tmp_path: Path,
) -> None:
    path = tmp_path / "package.nsp"
    path.write_bytes(
        _pfs0(
            (
                (
                    "entry.nca",
                    b"1234",
                ),
            )
        )
    )

    entry = parse_pfs0(path).entries[0]

    with pytest.raises(
        SwitchContainerError,
        match="offset must not be negative",
    ):
        read_entry_range(
            path,
            entry,
            offset=-1,
            size=1,
            max_size=1,
        )


def test_read_entry_range_rejects_negative_size(
    tmp_path: Path,
) -> None:
    path = tmp_path / "package.nsp"
    path.write_bytes(
        _pfs0(
            (
                (
                    "entry.nca",
                    b"1234",
                ),
            )
        )
    )

    entry = parse_pfs0(path).entries[0]

    with pytest.raises(
        SwitchContainerError,
        match="size must not be negative",
    ):
        read_entry_range(
            path,
            entry,
            offset=0,
            size=-1,
            max_size=1,
        )


def test_read_entry_range_rejects_entry_overrun(
    tmp_path: Path,
) -> None:
    path = tmp_path / "package.nsp"
    path.write_bytes(
        _pfs0(
            (
                (
                    "entry.nca",
                    b"1234",
                ),
            )
        )
    )

    entry = parse_pfs0(path).entries[0]

    with pytest.raises(
        SwitchContainerError,
        match="extends beyond the entry",
    ):
        read_entry_range(
            path,
            entry,
            offset=3,
            size=2,
            max_size=2,
        )


def test_find_entry_rejects_casefold_duplicate(
    tmp_path: Path,
) -> None:
    path = tmp_path / "package.nsp"

    path.write_bytes(
        _pfs0(
            (
                (
                    "ENTRY.NCA",
                    b"A",
                ),
                (
                    "entry.nca",
                    b"B",
                ),
            )
        )
    )

    table = parse_pfs0(path)

    with pytest.raises(
        SwitchContainerError,
        match="duplicate entry name",
    ):
        find_entry(
            table,
            "entry.nca",
        )
