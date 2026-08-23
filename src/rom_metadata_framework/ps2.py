from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .detection import (
    PlatformCandidate,
    PlatformDetection,
    PlatformEvidence,
)

ISO_SECTOR_SIZE = 2048
ISO_PVD_SECTOR = 16
ISO_PVD_OFFSET = ISO_PVD_SECTOR * ISO_SECTOR_SIZE
ISO_PVD_SIZE = ISO_SECTOR_SIZE

ISO_STANDARD_IDENTIFIER = b"CD001"
SYSTEM_CNF_NAME = "SYSTEM.CNF"

MAX_ROOT_DIRECTORY_SIZE = 4 * 1024 * 1024
MAX_SYSTEM_CNF_SIZE = 64 * 1024

_PS2_SERIAL_RE = re.compile(
    r"(?i)([A-Z]{4})[_-](\d{3})\.(\d{2})"
)


class Ps2FormatError(RuntimeError):
    """Raised when PS2 disc structure cannot be parsed safely."""


@dataclass(frozen=True, slots=True)
class Ps2IsoMetadata:
    """Trustworthy structural metadata extracted from a PS2 ISO image."""

    volume_identifier: str
    boot_path: str
    product_code: str | None
    system_cnf_extent: int
    system_cnf_size: int


@dataclass(frozen=True, slots=True)
class _IsoDirectoryEntry:
    name: str
    extent: int
    size: int
    directory: bool


def _decode_ascii_field(value: bytes) -> str:
    return value.decode("ascii", errors="replace").rstrip(" \0")


def _read_both_endian_u16(
    data: bytes,
    offset: int,
    field_name: str,
) -> int:
    little = int.from_bytes(
        data[offset : offset + 2],
        "little",
    )
    big = int.from_bytes(
        data[offset + 2 : offset + 4],
        "big",
    )

    if little != big:
        raise Ps2FormatError(
            f"ISO9660 {field_name} endian values disagree"
        )

    return little


def _read_both_endian_u32(
    data: bytes,
    offset: int,
    field_name: str,
) -> int:
    little = int.from_bytes(
        data[offset : offset + 4],
        "little",
    )
    big = int.from_bytes(
        data[offset + 4 : offset + 8],
        "big",
    )

    if little != big:
        raise Ps2FormatError(
            f"ISO9660 {field_name} endian values disagree"
        )

    return little


def _validate_extent(
    path: Path,
    *,
    extent: int,
    size: int,
    field_name: str,
) -> None:
    file_size = path.stat().st_size
    offset = extent * ISO_SECTOR_SIZE

    if offset > file_size:
        raise Ps2FormatError(
            f"ISO9660 {field_name} extent lies beyond the file"
        )

    if size > file_size - offset:
        raise Ps2FormatError(
            f"ISO9660 {field_name} extends beyond the file"
        )


def _parse_directory_entry(
    data: bytes,
    offset: int,
) -> tuple[_IsoDirectoryEntry | None, int]:
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
        raise Ps2FormatError(
            "ISO9660 directory record extends beyond directory data"
        )

    record = data[offset:end]

    if len(record) < 34:
        raise Ps2FormatError(
            "ISO9660 directory record is shorter than required fields"
        )

    name_length = record[32]
    name_end = 33 + name_length

    if name_end > len(record):
        raise Ps2FormatError(
            "ISO9660 directory identifier is truncated"
        )

    extent = _read_both_endian_u32(
        record,
        2,
        "directory extent",
    )
    size = _read_both_endian_u32(
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
        name = _decode_ascii_field(raw_name)

    return (
        _IsoDirectoryEntry(
            name=name,
            extent=extent,
            size=size,
            directory=bool(flags & 0x02),
        ),
        end,
    )


def _find_root_file(
    path: Path,
    *,
    root_extent: int,
    root_size: int,
    wanted_name: str,
) -> _IsoDirectoryEntry | None:
    if root_size <= 0:
        raise Ps2FormatError(
            "ISO9660 root directory has invalid size"
        )

    if root_size > MAX_ROOT_DIRECTORY_SIZE:
        raise Ps2FormatError(
            "ISO9660 root directory exceeds bounded parser limit"
        )

    _validate_extent(
        path,
        extent=root_extent,
        size=root_size,
        field_name="root directory",
    )

    with path.open("rb") as handle:
        handle.seek(root_extent * ISO_SECTOR_SIZE)
        data = handle.read(root_size)

    if len(data) != root_size:
        raise Ps2FormatError(
            "ISO9660 root directory is truncated"
        )

    offset = 0

    while offset < len(data):
        entry, next_offset = _parse_directory_entry(
            data,
            offset,
        )

        if next_offset <= offset:
            raise Ps2FormatError(
                "ISO9660 directory parser made no forward progress"
            )

        offset = next_offset

        if entry is None or entry.directory:
            continue

        normalized = entry.name.split(";", 1)[0].upper()

        if normalized == wanted_name.upper():
            return entry

    return None


def _parse_system_cnf(data: bytes) -> tuple[str, str | None]:
    text = data.decode(
        "ascii",
        errors="replace",
    )

    boot_path = None

    for line in text.splitlines():
        stripped = line.strip()

        if not stripped or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)

        if key.strip().upper() != "BOOT2":
            continue

        boot_path = value.strip().strip("\"'")
        break

    if not boot_path:
        raise Ps2FormatError(
            "SYSTEM.CNF does not contain BOOT2"
        )

    match = _PS2_SERIAL_RE.search(boot_path)

    product_code = None

    if match is not None:
        prefix, first, second = match.groups()
        product_code = (
            f"{prefix.upper()}-{first}{second}"
        )

    return boot_path, product_code


def inspect_ps2_iso(
    path: Path,
) -> Ps2IsoMetadata:
    """Parse bounded PS2-specific ISO9660 structural metadata."""

    path = Path(path)

    if not path.is_file():
        raise Ps2FormatError(
            f"source is not a regular file: {path}"
        )

    with path.open("rb") as handle:
        handle.seek(ISO_PVD_OFFSET)
        pvd = handle.read(ISO_PVD_SIZE)

    if len(pvd) != ISO_PVD_SIZE:
        raise Ps2FormatError(
            "ISO9660 primary volume descriptor is truncated"
        )

    if (
        pvd[0] != 1
        or pvd[1:6] != ISO_STANDARD_IDENTIFIER
        or pvd[6] != 1
    ):
        raise Ps2FormatError(
            "ISO9660 primary volume descriptor is not present"
        )

    logical_block_size = _read_both_endian_u16(
        pvd,
        128,
        "logical block size",
    )

    if logical_block_size != ISO_SECTOR_SIZE:
        raise Ps2FormatError(
            "ISO9660 logical block size is not 2048 bytes"
        )

    volume_identifier = _decode_ascii_field(
        pvd[40:72]
    )

    root_record_length = pvd[156]

    if root_record_length < 34:
        raise Ps2FormatError(
            "ISO9660 root directory record is invalid"
        )

    root_record = pvd[
        156 : 156 + root_record_length
    ]

    if len(root_record) != root_record_length:
        raise Ps2FormatError(
            "ISO9660 root directory record is truncated"
        )

    root_extent = _read_both_endian_u32(
        root_record,
        2,
        "root directory extent",
    )
    root_size = _read_both_endian_u32(
        root_record,
        10,
        "root directory size",
    )

    system_cnf = _find_root_file(
        path,
        root_extent=root_extent,
        root_size=root_size,
        wanted_name=SYSTEM_CNF_NAME,
    )

    if system_cnf is None:
        raise Ps2FormatError(
            "ISO9660 root does not contain SYSTEM.CNF"
        )

    if system_cnf.size <= 0:
        raise Ps2FormatError(
            "SYSTEM.CNF has invalid size"
        )

    if system_cnf.size > MAX_SYSTEM_CNF_SIZE:
        raise Ps2FormatError(
            "SYSTEM.CNF exceeds bounded parser limit"
        )

    _validate_extent(
        path,
        extent=system_cnf.extent,
        size=system_cnf.size,
        field_name="SYSTEM.CNF",
    )

    with path.open("rb") as handle:
        handle.seek(
            system_cnf.extent * ISO_SECTOR_SIZE
        )
        system_data = handle.read(system_cnf.size)

    if len(system_data) != system_cnf.size:
        raise Ps2FormatError(
            "SYSTEM.CNF is truncated"
        )

    boot_path, product_code = _parse_system_cnf(
        system_data
    )

    return Ps2IsoMetadata(
        volume_identifier=volume_identifier,
        boot_path=boot_path,
        product_code=product_code,
        system_cnf_extent=system_cnf.extent,
        system_cnf_size=system_cnf.size,
    )


class Ps2PlatformDetector:
    """Detect PS2 discs from ISO9660 + SYSTEM.CNF BOOT2 evidence."""

    name = "ps2"

    def detect(
        self,
        path: Path,
    ) -> PlatformDetection:
        """Return PS2 platform evidence from bounded disc parsing."""

        path = Path(path)

        try:
            metadata = inspect_ps2_iso(path)
        except (
            OSError,
            Ps2FormatError,
        ):
            return PlatformDetection()

        details = {
            "filesystem": "iso9660",
            "volume_identifier": (
                metadata.volume_identifier
            ),
            "boot_path": metadata.boot_path,
        }

        if metadata.product_code is not None:
            details["product_code"] = (
                metadata.product_code
            )

        evidence = PlatformEvidence(
            source="ps2-system-cnf",
            method="boot2",
            value=metadata.boot_path,
            strength=100,
            details=details,
        )

        return PlatformDetection(
            candidates=(
                PlatformCandidate(
                    platform="playstation-2",
                    confidence=100,
                    evidence=(evidence,),
                ),
            ),
        )
