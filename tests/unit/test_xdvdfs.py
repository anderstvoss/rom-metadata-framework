from pathlib import Path

import pytest

from rom_metadata_framework.xdvdfs import (
    XDVDFS_MAGIC,
    XDVDFS_SECTOR_SIZE,
    BoundedXdvdfs,
    XdvdfsFormatError,
)


def _node(
    *,
    name: str,
    sector: int,
    size: int,
    attributes: int = 0x80,
    left: int = 0,
    right: int = 0,
) -> bytes:
    encoded = name.encode("ascii")

    data = bytearray(
        14 + len(encoded)
    )

    data[0:2] = left.to_bytes(
        2,
        "little",
    )
    data[2:4] = right.to_bytes(
        2,
        "little",
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


def _write_image(
    path: Path,
    *,
    partition_offset: int = 0,
) -> None:
    descriptor_offset = (
        partition_offset
        + 32 * XDVDFS_SECTOR_SIZE
    )

    root_sector = 40
    file_sector = 41

    root = _node(
        name="default.xex",
        sector=file_sector,
        size=8,
    )

    root_data = root.ljust(
        XDVDFS_SECTOR_SIZE,
        b"\x00",
    )

    total_size = (
        partition_offset
        + 42 * XDVDFS_SECTOR_SIZE
    )

    image = bytearray(total_size)

    descriptor = bytearray(
        XDVDFS_SECTOR_SIZE
    )

    descriptor[:20] = XDVDFS_MAGIC
    descriptor[0x7EC:0x800] = (
        XDVDFS_MAGIC
    )

    descriptor[0x14:0x18] = (
        root_sector.to_bytes(
            4,
            "little",
        )
    )
    descriptor[0x18:0x1C] = (
        XDVDFS_SECTOR_SIZE.to_bytes(
            4,
            "little",
        )
    )

    image[
        descriptor_offset:
        descriptor_offset
        + XDVDFS_SECTOR_SIZE
    ] = descriptor

    root_offset = (
        partition_offset
        + root_sector * XDVDFS_SECTOR_SIZE
    )

    image[
        root_offset:
        root_offset
        + XDVDFS_SECTOR_SIZE
    ] = root_data

    file_offset = (
        partition_offset
        + file_sector * XDVDFS_SECTOR_SIZE
    )

    image[
        file_offset:
        file_offset + 8
    ] = b"XEX2test"

    path.write_bytes(image)


def test_reads_root_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"
    _write_image(path)

    fs = BoundedXdvdfs(path)

    entry = fs.find(
        "/default.xex"
    )

    assert entry is not None
    assert entry.name == "default.xex"
    assert entry.directory is False

    assert fs.read_file(
        "/DEFAULT.XEX",
        max_size=16,
    ) == b"XEX2test"


def test_detects_known_partition_offset(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"

    partition = 0x0000FB20

    _write_image(
        path,
        partition_offset=partition,
    )

    fs = BoundedXdvdfs(path)

    assert (
        fs.volume.partition_offset
        == partition
    )


def test_rejects_non_xdvdfs(
    tmp_path: Path,
) -> None:
    path = tmp_path / "garbage.bin"
    path.write_bytes(
        bytes(
            64 * XDVDFS_SECTOR_SIZE
        )
    )

    with pytest.raises(
        XdvdfsFormatError,
        match="volume descriptor",
    ):
        BoundedXdvdfs(path)


def test_rejects_missing_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"
    _write_image(path)

    fs = BoundedXdvdfs(path)

    assert fs.find(
        "/missing.bin"
    ) is None


def test_file_read_obeys_bound(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"
    _write_image(path)

    fs = BoundedXdvdfs(path)

    with pytest.raises(
        XdvdfsFormatError,
        match="bounded parser limit",
    ):
        fs.read_file(
            "/default.xex",
            max_size=4,
        )


def test_rejects_bad_closing_magic(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"
    _write_image(path)

    image = bytearray(
        path.read_bytes()
    )

    descriptor_offset = (
        32 * XDVDFS_SECTOR_SIZE
    )

    image[
        descriptor_offset
        + 0x7EC:
        descriptor_offset
        + 0x800
    ] = bytes(20)

    path.write_bytes(image)

    with pytest.raises(
        XdvdfsFormatError,
        match="volume descriptor",
    ):
        BoundedXdvdfs(path)


def test_reads_bounded_file_range(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"
    _write_image(path)

    fs = BoundedXdvdfs(path)

    assert fs.read_file_range(
        "/default.xex",
        offset=0,
        size=4,
        max_size=4,
    ) == b"XEX2"


def test_file_range_rejects_beyond_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"
    _write_image(path)

    fs = BoundedXdvdfs(path)

    with pytest.raises(
        XdvdfsFormatError,
        match="extends beyond file",
    ):
        fs.read_file_range(
            "/default.xex",
            offset=4,
            size=8,
            max_size=8,
        )


def test_rejects_root_extent_beyond_image(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bad.iso"
    _write_image(path)

    image = bytearray(
        path.read_bytes()
    )

    descriptor_offset = (
        32 * XDVDFS_SECTOR_SIZE
    )

    image[
        descriptor_offset
        + 0x14:
        descriptor_offset
        + 0x18
    ] = (
        0x7FFFFFFF
    ).to_bytes(
        4,
        "little",
    )

    path.write_bytes(image)

    with pytest.raises(
        XdvdfsFormatError,
        match="extent lies beyond",
    ):
        BoundedXdvdfs(path)


def test_rejects_root_size_above_bound(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bad.iso"
    _write_image(path)

    image = bytearray(
        path.read_bytes()
    )

    descriptor_offset = (
        32 * XDVDFS_SECTOR_SIZE
    )

    image[
        descriptor_offset
        + 0x18:
        descriptor_offset
        + 0x1C
    ] = (
        9 * 1024 * 1024
    ).to_bytes(
        4,
        "little",
    )

    path.write_bytes(image)

    with pytest.raises(
        XdvdfsFormatError,
        match="bounded parser limit",
    ):
        BoundedXdvdfs(path)


def test_file_range_rejects_negative_offset(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"
    _write_image(path)

    fs = BoundedXdvdfs(path)

    with pytest.raises(
        XdvdfsFormatError,
        match="must not be negative",
    ):
        fs.read_file_range(
            "/default.xex",
            offset=-1,
            size=1,
        )


def test_file_range_rejects_requested_bound(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"
    _write_image(path)

    fs = BoundedXdvdfs(path)

    with pytest.raises(
        XdvdfsFormatError,
        match="bounded parser limit",
    ):
        fs.read_file_range(
            "/default.xex",
            offset=0,
            size=5,
            max_size=4,
        )


def test_rejects_non_file_source(
    tmp_path: Path,
) -> None:
    path = tmp_path / "missing.iso"

    with pytest.raises(
        XdvdfsFormatError,
        match="not a regular file",
    ):
        BoundedXdvdfs(path)


def test_rejects_zero_root_size(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bad.iso"
    _write_image(path)

    image = bytearray(
        path.read_bytes()
    )

    descriptor_offset = (
        32 * XDVDFS_SECTOR_SIZE
    )

    image[
        descriptor_offset
        + 0x18:
        descriptor_offset
        + 0x1C
    ] = bytes(4)

    path.write_bytes(image)

    with pytest.raises(
        XdvdfsFormatError,
        match="invalid size",
    ):
        BoundedXdvdfs(path)


def test_custom_directory_bound_is_enforced(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"
    _write_image(path)

    with pytest.raises(
        XdvdfsFormatError,
        match="bounded parser limit",
    ):
        BoundedXdvdfs(
            path,
            max_directory_size=1024,
        )


def test_partition_probe_skips_invalid_candidates(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"
    _write_image(path)

    fs = BoundedXdvdfs(
        path,
        partition_offsets=(
            -1,
            0x7FFFFFFF,
            0,
        ),
    )

    assert (
        fs.volume.partition_offset
        == 0
    )


def test_rejects_root_extent_that_extends_beyond_image(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bad.iso"
    _write_image(path)

    image = bytearray(
        path.read_bytes()
    )

    descriptor_offset = (
        32 * XDVDFS_SECTOR_SIZE
    )

    image[
        descriptor_offset
        + 0x14:
        descriptor_offset
        + 0x18
    ] = (
        41
    ).to_bytes(
        4,
        "little",
    )

    image[
        descriptor_offset
        + 0x18:
        descriptor_offset
        + 0x1C
    ] = (
        2 * XDVDFS_SECTOR_SIZE
    ).to_bytes(
        4,
        "little",
    )

    path.write_bytes(image)

    with pytest.raises(
        XdvdfsFormatError,
        match="extends beyond the file",
    ):
        BoundedXdvdfs(path)


def test_list_directory_rejects_regular_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"
    _write_image(path)

    fs = BoundedXdvdfs(path)

    entry = fs.find(
        "/default.xex"
    )

    assert entry is not None

    with pytest.raises(
        XdvdfsFormatError,
        match="is not a directory",
    ):
        fs.list_directory(entry)


def test_directory_node_count_bound_is_enforced(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"
    _write_image(path)

    fs = BoundedXdvdfs(
        path,
        max_directory_nodes=0,
    )

    with pytest.raises(
        XdvdfsFormatError,
        match="node count exceeds",
    ):
        fs.list_directory()


def test_rejects_directory_child_outside_table(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bad.iso"
    _write_image(path)

    image = bytearray(
        path.read_bytes()
    )

    root_offset = (
        40 * XDVDFS_SECTOR_SIZE
    )

    # Right-child offsets are stored in 4-byte units.
    # 510 * 4 = 2040, leaving fewer than the required
    # 14 bytes for an XDVDFS directory node.
    image[
        root_offset + 2:
        root_offset + 4
    ] = (
        510
    ).to_bytes(
        2,
        "little",
    )

    path.write_bytes(image)

    fs = BoundedXdvdfs(path)

    with pytest.raises(
        XdvdfsFormatError,
        match="node lies outside",
    ):
        fs.list_directory()


def test_rejects_non_ascii_filename(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bad.iso"
    _write_image(path)

    image = bytearray(
        path.read_bytes()
    )

    root_offset = (
        40 * XDVDFS_SECTOR_SIZE
    )

    image[
        root_offset + 14
    ] = 0xFF

    path.write_bytes(image)

    fs = BoundedXdvdfs(path)

    with pytest.raises(
        XdvdfsFormatError,
        match="not valid ASCII",
    ):
        fs.list_directory()


def test_rejects_empty_filename(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bad.iso"
    _write_image(path)

    image = bytearray(
        path.read_bytes()
    )

    root_offset = (
        40 * XDVDFS_SECTOR_SIZE
    )

    image[
        root_offset + 13
    ] = 0

    path.write_bytes(image)

    fs = BoundedXdvdfs(path)

    with pytest.raises(
        XdvdfsFormatError,
        match="empty filename",
    ):
        fs.list_directory()


def test_find_rejects_descending_through_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"
    _write_image(path)

    fs = BoundedXdvdfs(path)

    assert (
        fs.find(
            "/default.xex/child"
        )
        is None
    )


def test_read_file_rejects_missing_path(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"
    _write_image(path)

    fs = BoundedXdvdfs(path)

    with pytest.raises(
        XdvdfsFormatError,
        match="path is not present",
    ):
        fs.read_file(
            "/missing.bin"
        )


def test_file_range_rejects_negative_size(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"
    _write_image(path)

    fs = BoundedXdvdfs(path)

    with pytest.raises(
        XdvdfsFormatError,
        match="size must not be negative",
    ):
        fs.read_file_range(
            "/default.xex",
            offset=0,
            size=-1,
        )


def test_file_range_rejects_missing_path(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"
    _write_image(path)

    fs = BoundedXdvdfs(path)

    with pytest.raises(
        XdvdfsFormatError,
        match="path is not present",
    ):
        fs.read_file_range(
            "/missing.bin",
            offset=0,
            size=1,
        )


def test_file_range_rejects_offset_beyond_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.iso"
    _write_image(path)

    fs = BoundedXdvdfs(path)

    with pytest.raises(
        XdvdfsFormatError,
        match="starts beyond file",
    ):
        fs.read_file_range(
            "/default.xex",
            offset=9,
            size=0,
        )
