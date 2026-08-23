from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

XDVDFS_SECTOR_SIZE = 2048
XDVDFS_MAGIC = b"MICROSOFT*XBOX*MEDIA"

# Known game-partition offsets used by established Xbox/Xbox 360
# disc readers. Detection remains bounded and never scans the image.
DEFAULT_PARTITION_OFFSETS = (
    0x00000000,
    0x0000FB20,
    0x00020600,
    0x02080000,
    0x0FD90000,
)

DEFAULT_MAX_DIRECTORY_SIZE = 8 * 1024 * 1024
DEFAULT_MAX_FILE_SIZE = 1024 * 1024
DEFAULT_MAX_DIRECTORY_NODES = 4096


class XdvdfsFormatError(RuntimeError):
    """Raised when bounded XDVDFS structure cannot be parsed safely."""


@dataclass(frozen=True, slots=True)
class XdvdfsDirectoryEntry:
    """One XDVDFS directory entry."""

    name: str
    sector: int
    size: int
    attributes: int

    @property
    def directory(self) -> bool:
        """Return whether the entry is a directory."""

        return bool(self.attributes & 0x10)


@dataclass(frozen=True, slots=True)
class XdvdfsVolumeDescriptor:
    """Validated XDVDFS volume descriptor."""

    partition_offset: int
    descriptor_offset: int
    root_sector: int
    root_size: int


def _u16le(data: bytes, offset: int) -> int:
    return int.from_bytes(
        data[offset : offset + 2],
        "little",
    )


def _u32le(data: bytes, offset: int) -> int:
    return int.from_bytes(
        data[offset : offset + 4],
        "little",
    )


class BoundedXdvdfs:
    """Bounded random-access reader for XDVDFS filesystem metadata."""

    def __init__(
        self,
        path: Path,
        *,
        partition_offsets: tuple[int, ...] = DEFAULT_PARTITION_OFFSETS,
        max_directory_size: int = DEFAULT_MAX_DIRECTORY_SIZE,
        max_directory_nodes: int = DEFAULT_MAX_DIRECTORY_NODES,
    ) -> None:
        self.path = Path(path)
        self.max_directory_size = max_directory_size
        self.max_directory_nodes = max_directory_nodes

        if not self.path.is_file():
            raise XdvdfsFormatError(
                f"source is not a regular file: {self.path}"
            )

        self.file_size = self.path.stat().st_size

        descriptor = None

        for partition_offset in partition_offsets:
            candidate = self._read_descriptor(
                partition_offset
            )

            if candidate is not None:
                descriptor = candidate
                break

        if descriptor is None:
            raise XdvdfsFormatError(
                "XDVDFS volume descriptor is not present"
            )

        self.volume = descriptor

    def _read_descriptor(
        self,
        partition_offset: int,
    ) -> XdvdfsVolumeDescriptor | None:
        if partition_offset < 0:
            return None

        descriptor_offset = (
            partition_offset
            + 32 * XDVDFS_SECTOR_SIZE
        )

        if (
            descriptor_offset
            > self.file_size
            or XDVDFS_SECTOR_SIZE
            > self.file_size - descriptor_offset
        ):
            return None

        with self.path.open("rb") as handle:
            handle.seek(descriptor_offset)
            data = handle.read(
                XDVDFS_SECTOR_SIZE
            )

        if len(data) != XDVDFS_SECTOR_SIZE:
            return None

        if data[:20] != XDVDFS_MAGIC:
            return None

        if data[0x7EC:0x800] != XDVDFS_MAGIC:
            return None

        root_sector = _u32le(
            data,
            0x14,
        )
        root_size = _u32le(
            data,
            0x18,
        )

        if root_size <= 0:
            raise XdvdfsFormatError(
                "XDVDFS root directory has invalid size"
            )

        if root_size > self.max_directory_size:
            raise XdvdfsFormatError(
                "XDVDFS root directory exceeds bounded parser limit"
            )

        self._validate_extent(
            partition_offset=partition_offset,
            sector=root_sector,
            size=root_size,
            field_name="root directory",
        )

        return XdvdfsVolumeDescriptor(
            partition_offset=partition_offset,
            descriptor_offset=descriptor_offset,
            root_sector=root_sector,
            root_size=root_size,
        )

    def _validate_extent(
        self,
        *,
        partition_offset: int,
        sector: int,
        size: int,
        field_name: str,
    ) -> int:
        offset = (
            partition_offset
            + sector * XDVDFS_SECTOR_SIZE
        )

        if offset > self.file_size:
            raise XdvdfsFormatError(
                f"XDVDFS {field_name} extent lies beyond the file"
            )

        if size > self.file_size - offset:
            raise XdvdfsFormatError(
                f"XDVDFS {field_name} extends beyond the file"
            )

        return offset

    def _read_directory_table(
        self,
        entry: XdvdfsDirectoryEntry | None = None,
    ) -> bytes:
        if entry is None:
            sector = self.volume.root_sector
            size = self.volume.root_size
            field_name = "root directory"
        else:
            if not entry.directory:
                raise XdvdfsFormatError(
                    f"XDVDFS {entry.name} is not a directory"
                )

            sector = entry.sector
            size = entry.size
            field_name = f"{entry.name} directory"

        if size <= 0:
            raise XdvdfsFormatError(
                f"XDVDFS {field_name} has invalid size"
            )

        if size > self.max_directory_size:
            raise XdvdfsFormatError(
                f"XDVDFS {field_name} exceeds bounded parser limit"
            )

        offset = self._validate_extent(
            partition_offset=self.volume.partition_offset,
            sector=sector,
            size=size,
            field_name=field_name,
        )

        with self.path.open("rb") as handle:
            handle.seek(offset)
            data = handle.read(size)

        if len(data) != size:
            raise XdvdfsFormatError(
                f"XDVDFS {field_name} is truncated"
            )

        return data

    def list_directory(
        self,
        entry: XdvdfsDirectoryEntry | None = None,
    ) -> tuple[XdvdfsDirectoryEntry, ...]:
        """Read one bounded XDVDFS directory AVL tree."""

        data = self._read_directory_table(entry)

        seen: set[int] = set()
        entries: list[XdvdfsDirectoryEntry] = []

        def walk(offset: int) -> None:
            if offset in seen:
                return

            if len(seen) >= self.max_directory_nodes:
                raise XdvdfsFormatError(
                    "XDVDFS directory node count exceeds bounded limit"
                )

            if offset < 0 or offset + 14 > len(data):
                raise XdvdfsFormatError(
                    "XDVDFS directory node lies outside directory data"
                )

            seen.add(offset)

            left = _u16le(
                data,
                offset,
            )
            right = _u16le(
                data,
                offset + 2,
            )
            sector = _u32le(
                data,
                offset + 4,
            )
            size = _u32le(
                data,
                offset + 8,
            )
            attributes = data[offset + 12]
            name_length = data[offset + 13]

            name_start = offset + 14
            name_end = name_start + name_length

            if name_end > len(data):
                raise XdvdfsFormatError(
                    "XDVDFS filename extends beyond directory data"
                )

            raw_name = data[
                name_start:name_end
            ]

            try:
                name = raw_name.decode(
                    "ascii",
                    errors="strict",
                )
            except UnicodeDecodeError as exc:
                raise XdvdfsFormatError(
                    "XDVDFS filename is not valid ASCII"
                ) from exc

            if not name:
                raise XdvdfsFormatError(
                    "XDVDFS directory entry has empty filename"
                )

            entries.append(
                XdvdfsDirectoryEntry(
                    name=name,
                    sector=sector,
                    size=size,
                    attributes=attributes,
                )
            )

            if left:
                walk(left * 4)

            if right:
                walk(right * 4)

        walk(0)

        return tuple(entries)

    def find(
        self,
        path: str,
    ) -> XdvdfsDirectoryEntry | None:
        """Find one case-insensitive path."""

        parts = tuple(
            part
            for part in path.strip("/").split("/")
            if part
        )

        if not parts:
            return None

        directory: XdvdfsDirectoryEntry | None = None

        for index, part in enumerate(parts):
            wanted = part.casefold()

            match = next(
                (
                    candidate
                    for candidate in self.list_directory(
                        directory
                    )
                    if candidate.name.casefold()
                    == wanted
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

            directory = match

        return directory

    def read_file_range(
        self,
        path: str,
        *,
        offset: int,
        size: int,
        max_size: int = DEFAULT_MAX_FILE_SIZE,
    ) -> bytes:
        """Read one bounded byte range from a regular file."""

        if offset < 0:
            raise XdvdfsFormatError(
                "XDVDFS file range offset must not be negative"
            )

        if size < 0:
            raise XdvdfsFormatError(
                "XDVDFS file range size must not be negative"
            )

        if size > max_size:
            raise XdvdfsFormatError(
                f"XDVDFS {path} range exceeds bounded parser limit"
            )

        entry = self.find(path)

        if entry is None:
            raise XdvdfsFormatError(
                f"XDVDFS path is not present: {path}"
            )

        if entry.directory:
            raise XdvdfsFormatError(
                f"XDVDFS path is a directory: {path}"
            )

        if offset > entry.size:
            raise XdvdfsFormatError(
                f"XDVDFS {path} range starts beyond file"
            )

        if size > entry.size - offset:
            raise XdvdfsFormatError(
                f"XDVDFS {path} range extends beyond file"
            )

        file_offset = self._validate_extent(
            partition_offset=self.volume.partition_offset,
            sector=entry.sector,
            size=entry.size,
            field_name=path,
        )

        with self.path.open("rb") as handle:
            handle.seek(
                file_offset + offset
            )
            data = handle.read(size)

        if len(data) != size:
            raise XdvdfsFormatError(
                f"XDVDFS {path} range is truncated"
            )

        return data

    def read_file(
        self,
        path: str,
        *,
        max_size: int = DEFAULT_MAX_FILE_SIZE,
    ) -> bytes:
        """Read one bounded regular file."""

        entry = self.find(path)

        if entry is None:
            raise XdvdfsFormatError(
                f"XDVDFS path is not present: {path}"
            )

        if entry.directory:
            raise XdvdfsFormatError(
                f"XDVDFS path is a directory: {path}"
            )

        if entry.size <= 0:
            raise XdvdfsFormatError(
                f"XDVDFS {path} has invalid size"
            )

        if entry.size > max_size:
            raise XdvdfsFormatError(
                f"XDVDFS {path} exceeds bounded parser limit"
            )

        offset = self._validate_extent(
            partition_offset=self.volume.partition_offset,
            sector=entry.sector,
            size=entry.size,
            field_name=path,
        )

        with self.path.open("rb") as handle:
            handle.seek(offset)
            data = handle.read(entry.size)

        if len(data) != entry.size:
            raise XdvdfsFormatError(
                f"XDVDFS {path} is truncated"
            )

        return data
