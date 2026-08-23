from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ISO_SECTOR_SIZE = 2048
ISO_PVD_SECTOR = 16
ISO_PVD_OFFSET = ISO_PVD_SECTOR * ISO_SECTOR_SIZE
ISO_PVD_SIZE = ISO_SECTOR_SIZE
ISO_STANDARD_IDENTIFIER = b"CD001"

DEFAULT_MAX_DIRECTORY_SIZE = 8 * 1024 * 1024
DEFAULT_MAX_FILE_SIZE = 1024 * 1024


class Iso9660FormatError(RuntimeError):
    """Raised when bounded ISO9660 structure cannot be parsed safely."""


@dataclass(frozen=True, slots=True)
class Iso9660DirectoryEntry:
    """One ISO9660 directory entry."""

    name: str
    extent: int
    size: int
    directory: bool


def decode_ascii_field(value: bytes) -> str:
    """Decode one fixed-width ISO9660 ASCII field."""

    return value.decode(
        "ascii",
        errors="replace",
    ).rstrip(" \0")


def read_both_endian_u16(
    data: bytes,
    offset: int,
    field_name: str,
) -> int:
    """Decode an ISO9660 both-endian 16-bit integer."""

    little = int.from_bytes(
        data[offset : offset + 2],
        "little",
    )
    big = int.from_bytes(
        data[offset + 2 : offset + 4],
        "big",
    )

    if little != big:
        raise Iso9660FormatError(
            f"ISO9660 {field_name} endian values disagree"
        )

    return little


def read_both_endian_u32(
    data: bytes,
    offset: int,
    field_name: str,
) -> int:
    """Decode an ISO9660 both-endian 32-bit integer."""

    little = int.from_bytes(
        data[offset : offset + 4],
        "little",
    )
    big = int.from_bytes(
        data[offset + 4 : offset + 8],
        "big",
    )

    if little != big:
        raise Iso9660FormatError(
            f"ISO9660 {field_name} endian values disagree"
        )

    return little


def parse_directory_entry(
    data: bytes,
    offset: int,
) -> tuple[Iso9660DirectoryEntry | None, int]:
    """Parse one directory record and return the next offset."""

    if offset >= len(data):
        return None, len(data)

    record_length = data[offset]

    if record_length == 0:
        next_sector = (
            ((offset // ISO_SECTOR_SIZE) + 1)
            * ISO_SECTOR_SIZE
        )
        return None, min(next_sector, len(data))

    end = offset + record_length

    if end > len(data):
        raise Iso9660FormatError(
            "ISO9660 directory record extends beyond directory data"
        )

    record = data[offset:end]

    if len(record) < 34:
        raise Iso9660FormatError(
            "ISO9660 directory record is shorter than required fields"
        )

    name_length = record[32]
    name_end = 33 + name_length

    if name_end > len(record):
        raise Iso9660FormatError(
            "ISO9660 directory identifier is truncated"
        )

    extent = read_both_endian_u32(
        record,
        2,
        "directory extent",
    )
    size = read_both_endian_u32(
        record,
        10,
        "directory size",
    )
    flags = record[25]

    raw_name = record[33:name_end]

    if raw_name == b"\x00":
        name = "."
    elif raw_name == b"\x01":
        name = ".."
    else:
        name = decode_ascii_field(raw_name).split(";", 1)[0]

    return (
        Iso9660DirectoryEntry(
            name=name,
            extent=extent,
            size=size,
            directory=bool(flags & 0x02),
        ),
        end,
    )


class BoundedIso9660:
    """Bounded random-access reader for simple ISO9660 structures."""

    def __init__(
        self,
        path: Path,
        *,
        max_directory_size: int = DEFAULT_MAX_DIRECTORY_SIZE,
    ) -> None:
        self.path = Path(path)
        self.max_directory_size = max_directory_size

        if not self.path.is_file():
            raise Iso9660FormatError(
                f"source is not a regular file: {self.path}"
            )

        self.file_size = self.path.stat().st_size

        with self.path.open("rb") as handle:
            handle.seek(ISO_PVD_OFFSET)
            pvd = handle.read(ISO_PVD_SIZE)

        if len(pvd) != ISO_PVD_SIZE:
            raise Iso9660FormatError(
                "ISO9660 primary volume descriptor is truncated"
            )

        if (
            pvd[0] != 1
            or pvd[1:6] != ISO_STANDARD_IDENTIFIER
            or pvd[6] != 1
        ):
            raise Iso9660FormatError(
                "ISO9660 primary volume descriptor is not present"
            )

        logical_block_size = read_both_endian_u16(
            pvd,
            128,
            "logical block size",
        )

        if logical_block_size != ISO_SECTOR_SIZE:
            raise Iso9660FormatError(
                "ISO9660 logical block size is not 2048 bytes"
            )

        self.volume_identifier = decode_ascii_field(
            pvd[40:72]
        )

        root_record_length = pvd[156]

        if root_record_length < 34:
            raise Iso9660FormatError(
                "ISO9660 root directory record is invalid"
            )

        root_record = pvd[
            156 : 156 + root_record_length
        ]

        if len(root_record) != root_record_length:
            raise Iso9660FormatError(
                "ISO9660 root directory record is truncated"
            )

        self.root = Iso9660DirectoryEntry(
            name="root",
            extent=read_both_endian_u32(
                root_record,
                2,
                "root directory extent",
            ),
            size=read_both_endian_u32(
                root_record,
                10,
                "root directory size",
            ),
            directory=True,
        )

    def validate_extent(
        self,
        *,
        extent: int,
        size: int,
        field_name: str,
    ) -> None:
        """Ensure one extent lies within the physical source."""

        offset = extent * ISO_SECTOR_SIZE

        if offset > self.file_size:
            raise Iso9660FormatError(
                f"ISO9660 {field_name} extent lies beyond the file"
            )

        if size > self.file_size - offset:
            raise Iso9660FormatError(
                f"ISO9660 {field_name} extends beyond the file"
            )

    def read_directory(
        self,
        entry: Iso9660DirectoryEntry,
    ) -> tuple[Iso9660DirectoryEntry, ...]:
        """Read one bounded directory."""

        if not entry.directory:
            raise Iso9660FormatError(
                f"ISO9660 {entry.name} is not a directory"
            )

        if entry.size <= 0:
            raise Iso9660FormatError(
                f"ISO9660 {entry.name} directory has invalid size"
            )

        if entry.size > self.max_directory_size:
            raise Iso9660FormatError(
                f"ISO9660 {entry.name} directory exceeds bounded parser limit"
            )

        self.validate_extent(
            extent=entry.extent,
            size=entry.size,
            field_name=f"{entry.name} directory",
        )

        with self.path.open("rb") as handle:
            handle.seek(
                entry.extent * ISO_SECTOR_SIZE
            )
            data = handle.read(entry.size)

        if len(data) != entry.size:
            raise Iso9660FormatError(
                f"ISO9660 {entry.name} directory is truncated"
            )

        entries = []
        offset = 0

        while offset < len(data):
            child, next_offset = parse_directory_entry(
                data,
                offset,
            )

            if next_offset <= offset:
                raise Iso9660FormatError(
                    "ISO9660 directory parser made no forward progress"
                )

            offset = next_offset

            if child is None or child.name in {".", ".."}:
                continue

            entries.append(child)

        return tuple(entries)

    def find(
        self,
        path: str,
    ) -> Iso9660DirectoryEntry | None:
        """Find one case-insensitive ISO9660 path."""

        parts = tuple(
            part
            for part in path.strip("/").split("/")
            if part
        )

        current = self.root

        for index, part in enumerate(parts):
            wanted = part.upper()

            match = next(
                (
                    entry
                    for entry in self.read_directory(current)
                    if entry.name.upper() == wanted
                ),
                None,
            )

            if match is None:
                return None

            if (
                index < len(parts) - 1
                and not match.directory
            ):
                return None

            current = match

        return current

    def read_file(
        self,
        path: str,
        *,
        max_size: int = DEFAULT_MAX_FILE_SIZE,
    ) -> bytes:
        """Read one bounded regular file."""

        entry = self.find(path)

        if entry is None:
            raise Iso9660FormatError(
                f"ISO9660 path is not present: {path}"
            )

        if entry.directory:
            raise Iso9660FormatError(
                f"ISO9660 path is a directory: {path}"
            )

        if entry.size <= 0:
            raise Iso9660FormatError(
                f"ISO9660 {path} has invalid size"
            )

        if entry.size > max_size:
            raise Iso9660FormatError(
                f"ISO9660 {path} exceeds bounded parser limit"
            )

        self.validate_extent(
            extent=entry.extent,
            size=entry.size,
            field_name=path,
        )

        with self.path.open("rb") as handle:
            handle.seek(
                entry.extent * ISO_SECTOR_SIZE
            )
            data = handle.read(entry.size)

        if len(data) != entry.size:
            raise Iso9660FormatError(
                f"ISO9660 {path} is truncated"
            )

        return data
