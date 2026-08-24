from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PFS0_MAGIC = b"PFS0"
HFS0_MAGIC = b"HFS0"
XCI_MAGIC = b"HEAD"

PFS0_ENTRY_SIZE = 0x18
HFS0_ENTRY_SIZE = 0x40

XCI_HEADER_SIZE = 0x200
XCI_MAGIC_OFFSET = 0x100
XCI_ROOT_HFS0_OFFSET_FIELD = 0x130

DEFAULT_MAX_FILE_COUNT = 4096
DEFAULT_MAX_STRING_TABLE_SIZE = 4 * 1024 * 1024


class SwitchContainerError(RuntimeError):
    """Raised when a Switch container cannot be parsed safely."""


@dataclass(frozen=True, slots=True)
class SwitchContainerEntry:
    """One bounded PFS0 or HFS0 entry."""

    name: str
    offset: int
    size: int
    hashed_size: int | None = None
    hash_hex: str | None = None


@dataclass(frozen=True, slots=True)
class SwitchContainerTable:
    """Bounded PFS0 or HFS0 directory table."""

    format: str
    offset: int
    data_offset: int
    entries: tuple[SwitchContainerEntry, ...]


@dataclass(frozen=True, slots=True)
class SwitchXciStructure:
    """Plaintext outer structure of an XCI image."""

    root_hfs0_offset: int
    root: SwitchContainerTable
    secure: SwitchContainerTable


def _source_size(
    path: Path,
) -> int:
    path = Path(path)

    if not path.is_file():
        raise SwitchContainerError(
            "Switch container source is not a regular file"
        )

    return path.stat().st_size


def _read_exact(
    handle,
    *,
    source_size: int,
    offset: int,
    size: int,
) -> bytes:
    if offset < 0:
        raise SwitchContainerError(
            "Switch container offset must not be negative"
        )

    if size < 0:
        raise SwitchContainerError(
            "Switch container read size must not be negative"
        )

    if offset + size > source_size:
        raise SwitchContainerError(
            "Switch container range extends beyond the source file"
        )

    handle.seek(offset)
    data = handle.read(size)

    if len(data) != size:
        raise SwitchContainerError(
            "Switch container range is truncated"
        )

    return data


def _read_name(
    table: bytes,
    offset: int,
) -> str:
    if not 0 <= offset < len(table):
        raise SwitchContainerError(
            "Switch container filename offset lies outside "
            "the string table"
        )

    end = table.find(
        b"\x00",
        offset,
    )

    if end < 0:
        raise SwitchContainerError(
            "Switch container filename is not null-terminated"
        )

    raw = table[offset:end]

    if not raw:
        raise SwitchContainerError(
            "Switch container filename must not be empty"
        )

    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SwitchContainerError(
            "Switch container filename is not valid UTF-8"
        ) from exc


def _validate_table_bounds(
    *,
    count: int,
    string_size: int,
    max_files: int,
    max_string_table_size: int,
) -> None:
    if count > max_files:
        raise SwitchContainerError(
            "Switch container file count exceeds bounded limit"
        )

    if string_size > max_string_table_size:
        raise SwitchContainerError(
            "Switch container string table exceeds bounded limit"
        )


def parse_pfs0(
    path: Path,
    *,
    offset: int = 0,
    max_files: int = DEFAULT_MAX_FILE_COUNT,
    max_string_table_size: int = (
        DEFAULT_MAX_STRING_TABLE_SIZE
    ),
) -> SwitchContainerTable:
    """Parse a bounded PFS0 file table."""

    path = Path(path)
    source_size = _source_size(path)

    with path.open("rb") as handle:
        fixed = _read_exact(
            handle,
            source_size=source_size,
            offset=offset,
            size=0x10,
        )

        if fixed[:4] != PFS0_MAGIC:
            raise SwitchContainerError(
                "PFS0 magic is missing"
            )

        count = int.from_bytes(
            fixed[4:8],
            "little",
        )
        string_size = int.from_bytes(
            fixed[8:12],
            "little",
        )

        _validate_table_bounds(
            count=count,
            string_size=string_size,
            max_files=max_files,
            max_string_table_size=(
                max_string_table_size
            ),
        )

        entries_size = (
            count * PFS0_ENTRY_SIZE
        )

        entries_raw = _read_exact(
            handle,
            source_size=source_size,
            offset=offset + 0x10,
            size=entries_size,
        )

        strings = _read_exact(
            handle,
            source_size=source_size,
            offset=(
                offset
                + 0x10
                + entries_size
            ),
            size=string_size,
        )

    data_offset = (
        offset
        + 0x10
        + entries_size
        + string_size
    )

    entries = []

    for index in range(count):
        start = (
            index * PFS0_ENTRY_SIZE
        )
        item = entries_raw[
            start:
            start + PFS0_ENTRY_SIZE
        ]

        relative = int.from_bytes(
            item[0x00:0x08],
            "little",
        )
        size = int.from_bytes(
            item[0x08:0x10],
            "little",
        )
        name_offset = int.from_bytes(
            item[0x10:0x14],
            "little",
        )

        name = _read_name(
            strings,
            name_offset,
        )

        absolute = (
            data_offset + relative
        )

        if absolute + size > source_size:
            raise SwitchContainerError(
                f"PFS0 extent for {name!r} extends "
                "beyond the source file"
            )

        entries.append(
            SwitchContainerEntry(
                name=name,
                offset=absolute,
                size=size,
            )
        )

    return SwitchContainerTable(
        format="pfs0",
        offset=offset,
        data_offset=data_offset,
        entries=tuple(entries),
    )


def parse_hfs0(
    path: Path,
    *,
    offset: int,
    max_files: int = DEFAULT_MAX_FILE_COUNT,
    max_string_table_size: int = (
        DEFAULT_MAX_STRING_TABLE_SIZE
    ),
) -> SwitchContainerTable:
    """Parse a bounded HFS0 file table."""

    path = Path(path)
    source_size = _source_size(path)

    with path.open("rb") as handle:
        fixed = _read_exact(
            handle,
            source_size=source_size,
            offset=offset,
            size=0x10,
        )

        if fixed[:4] != HFS0_MAGIC:
            raise SwitchContainerError(
                "HFS0 magic is missing"
            )

        count = int.from_bytes(
            fixed[4:8],
            "little",
        )
        string_size = int.from_bytes(
            fixed[8:12],
            "little",
        )

        _validate_table_bounds(
            count=count,
            string_size=string_size,
            max_files=max_files,
            max_string_table_size=(
                max_string_table_size
            ),
        )

        entries_size = (
            count * HFS0_ENTRY_SIZE
        )

        entries_raw = _read_exact(
            handle,
            source_size=source_size,
            offset=offset + 0x10,
            size=entries_size,
        )

        strings = _read_exact(
            handle,
            source_size=source_size,
            offset=(
                offset
                + 0x10
                + entries_size
            ),
            size=string_size,
        )

    data_offset = (
        offset
        + 0x10
        + entries_size
        + string_size
    )

    entries = []

    for index in range(count):
        start = (
            index * HFS0_ENTRY_SIZE
        )
        item = entries_raw[
            start:
            start + HFS0_ENTRY_SIZE
        ]

        relative = int.from_bytes(
            item[0x00:0x08],
            "little",
        )
        size = int.from_bytes(
            item[0x08:0x10],
            "little",
        )
        name_offset = int.from_bytes(
            item[0x10:0x14],
            "little",
        )
        hashed_size = int.from_bytes(
            item[0x14:0x18],
            "little",
        )
        digest = item[
            0x20:0x40
        ]

        name = _read_name(
            strings,
            name_offset,
        )

        absolute = (
            data_offset + relative
        )

        if absolute + size > source_size:
            raise SwitchContainerError(
                f"HFS0 extent for {name!r} extends "
                "beyond the source file"
            )

        if hashed_size > size:
            raise SwitchContainerError(
                f"HFS0 hashed size for {name!r} "
                "exceeds entry size"
            )

        entries.append(
            SwitchContainerEntry(
                name=name,
                offset=absolute,
                size=size,
                hashed_size=hashed_size,
                hash_hex=digest.hex(),
            )
        )

    return SwitchContainerTable(
        format="hfs0",
        offset=offset,
        data_offset=data_offset,
        entries=tuple(entries),
    )


def find_entry(
    table: SwitchContainerTable,
    name: str,
) -> SwitchContainerEntry | None:
    """Return one case-insensitive entry from a table."""

    normalized = name.casefold()

    matches = tuple(
        entry
        for entry in table.entries
        if entry.name.casefold()
        == normalized
    )

    if len(matches) > 1:
        raise SwitchContainerError(
            f"Switch container contains duplicate "
            f"entry name {name!r}"
        )

    if not matches:
        return None

    return matches[0]


def read_entry_range(
    path: Path,
    entry: SwitchContainerEntry,
    *,
    offset: int,
    size: int,
    max_size: int,
) -> bytes:
    """Read one explicitly bounded range from an entry."""

    if offset < 0:
        raise SwitchContainerError(
            "entry range offset must not be negative"
        )

    if size < 0:
        raise SwitchContainerError(
            "entry range size must not be negative"
        )

    if size > max_size:
        raise SwitchContainerError(
            "entry range exceeds bounded read limit"
        )

    if offset + size > entry.size:
        raise SwitchContainerError(
            "entry range extends beyond the entry"
        )

    path = Path(path)
    source_size = _source_size(path)

    with path.open("rb") as handle:
        return _read_exact(
            handle,
            source_size=source_size,
            offset=(
                entry.offset + offset
            ),
            size=size,
        )


def parse_xci(
    path: Path,
) -> SwitchXciStructure:
    """Parse bounded plaintext XCI outer structure."""

    path = Path(path)
    source_size = _source_size(path)

    with path.open("rb") as handle:
        header = _read_exact(
            handle,
            source_size=source_size,
            offset=0,
            size=XCI_HEADER_SIZE,
        )

    if (
        header[
            XCI_MAGIC_OFFSET:
            XCI_MAGIC_OFFSET + 4
        ]
        != XCI_MAGIC
    ):
        raise SwitchContainerError(
            "XCI HEAD magic is missing"
        )

    root_offset = int.from_bytes(
        header[
            XCI_ROOT_HFS0_OFFSET_FIELD:
            XCI_ROOT_HFS0_OFFSET_FIELD + 8
        ],
        "little",
    )

    if (
        root_offset < XCI_HEADER_SIZE
        or root_offset % 0x200 != 0
    ):
        raise SwitchContainerError(
            "XCI root HFS0 offset is invalid"
        )

    root = parse_hfs0(
        path,
        offset=root_offset,
        max_files=16,
    )

    secure_entry = find_entry(
        root,
        "secure",
    )

    if secure_entry is None:
        raise SwitchContainerError(
            "XCI root HFS0 does not contain secure partition"
        )

    secure = parse_hfs0(
        path,
        offset=secure_entry.offset,
    )

    return SwitchXciStructure(
        root_hfs0_offset=root_offset,
        root=root,
        secure=secure,
    )
