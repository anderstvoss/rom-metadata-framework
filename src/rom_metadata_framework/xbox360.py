from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .detection import (
    PlatformCandidate,
    PlatformDetection,
    PlatformEvidence,
)
from .inspection import StructuralInspectionResult
from .local_metadata import (
    LocalContentMetadata,
    LocalIdentifier,
    LocalMetadataProvenance,
    LocalMetadataValue,
)
from .representation import RepresentationIdentity
from .xdvdfs import (
    BoundedXdvdfs,
    XdvdfsFormatError,
)

XBOX360_DEFAULT_XEX_PATH = "/default.xex"

XEX2_MAGIC = b"XEX2"
XEX2_EXECUTION_ID_HEADER = 0x00040006

MAX_XEX_BASE_HEADER_SIZE = 24
MAX_XEX_OPTIONAL_HEADER_COUNT = 4096
MAX_XEX_OPTIONAL_TABLE_SIZE = (
    MAX_XEX_OPTIONAL_HEADER_COUNT * 8
)
MAX_XEX_EXECUTION_ID_SIZE = 20


class Xbox360FormatError(RuntimeError):
    """Raised when Xbox 360 executable metadata cannot be parsed safely."""


@dataclass(frozen=True, slots=True)
class Xbox360ExecutionId:
    """Xbox 360 XEX2 Execution ID."""

    media_id: str
    version: int
    base_version: int
    title_id: str
    platform: int
    executable_type: int
    disc_number: int
    disc_count: int


@dataclass(frozen=True, slots=True)
class Xbox360DiscMetadata:
    """Bounded structural metadata from an Xbox 360 disc image."""

    partition_offset: int
    descriptor_offset: int
    root_sector: int
    root_size: int
    xex_sector: int
    xex_size: int
    execution_id: Xbox360ExecutionId


def _u32be(
    data: bytes,
    offset: int,
) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise Xbox360FormatError(
            "XEX2 integer lies beyond bounded data"
        )

    return int.from_bytes(
        data[offset : offset + 4],
        "big",
    )


def _parse_execution_id(
    data: bytes,
) -> Xbox360ExecutionId:
    if len(data) != MAX_XEX_EXECUTION_ID_SIZE:
        raise Xbox360FormatError(
            "XEX2 Execution ID has invalid size"
        )

    return Xbox360ExecutionId(
        media_id=f"{_u32be(data, 0):08X}",
        version=_u32be(data, 4),
        base_version=_u32be(data, 8),
        title_id=f"{_u32be(data, 12):08X}",
        platform=data[16],
        executable_type=data[17],
        disc_number=data[18],
        disc_count=data[19],
    )


def inspect_xbox360_disc(
    path: Path,
) -> Xbox360DiscMetadata:
    """Inspect bounded XDVDFS/XEX2 metadata from an Xbox 360 disc."""

    try:
        filesystem = BoundedXdvdfs(
            Path(path)
        )

        xex_entry = filesystem.find(
            XBOX360_DEFAULT_XEX_PATH
        )

        if (
            xex_entry is None
            or xex_entry.directory
        ):
            raise Xbox360FormatError(
                "XDVDFS root does not contain default.xex"
            )

        base_header = filesystem.read_file_range(
            XBOX360_DEFAULT_XEX_PATH,
            offset=0,
            size=MAX_XEX_BASE_HEADER_SIZE,
            max_size=MAX_XEX_BASE_HEADER_SIZE,
        )

        if base_header[:4] != XEX2_MAGIC:
            raise Xbox360FormatError(
                "default.xex does not contain XEX2 magic"
            )

        header_count = _u32be(
            base_header,
            0x14,
        )

        if header_count > MAX_XEX_OPTIONAL_HEADER_COUNT:
            raise Xbox360FormatError(
                "XEX2 optional header count exceeds bounded limit"
            )

        table_size = header_count * 8

        optional_table = filesystem.read_file_range(
            XBOX360_DEFAULT_XEX_PATH,
            offset=0x18,
            size=table_size,
            max_size=MAX_XEX_OPTIONAL_TABLE_SIZE,
        )

        execution_offset = None

        for index in range(header_count):
            offset = index * 8

            key = _u32be(
                optional_table,
                offset,
            )
            value = _u32be(
                optional_table,
                offset + 4,
            )

            if key == XEX2_EXECUTION_ID_HEADER:
                if execution_offset is not None:
                    raise Xbox360FormatError(
                        "XEX2 contains duplicate Execution ID headers"
                    )

                execution_offset = value

        if execution_offset is None:
            raise Xbox360FormatError(
                "XEX2 Execution ID header is missing"
            )

        execution_data = filesystem.read_file_range(
            XBOX360_DEFAULT_XEX_PATH,
            offset=execution_offset,
            size=MAX_XEX_EXECUTION_ID_SIZE,
            max_size=MAX_XEX_EXECUTION_ID_SIZE,
        )

    except XdvdfsFormatError as exc:
        raise Xbox360FormatError(
            str(exc)
        ) from exc

    execution_id = _parse_execution_id(
        execution_data
    )

    if execution_id.disc_count == 0:
        raise Xbox360FormatError(
            "XEX2 Execution ID disc count is invalid"
        )

    if execution_id.disc_number == 0:
        raise Xbox360FormatError(
            "XEX2 Execution ID disc number is invalid"
        )

    if (
        execution_id.disc_number
        > execution_id.disc_count
    ):
        raise Xbox360FormatError(
            "XEX2 Execution ID disc number exceeds disc count"
        )

    return Xbox360DiscMetadata(
        partition_offset=(
            filesystem.volume.partition_offset
        ),
        descriptor_offset=(
            filesystem.volume.descriptor_offset
        ),
        root_sector=(
            filesystem.volume.root_sector
        ),
        root_size=(
            filesystem.volume.root_size
        ),
        xex_sector=xex_entry.sector,
        xex_size=xex_entry.size,
        execution_id=execution_id,
    )


class Xbox360PlatformDetector:
    """Detect Xbox 360 discs from XDVDFS + default.xex + XEX2 evidence."""

    name = "xbox360"

    def detect(
        self,
        path: Path,
    ) -> PlatformDetection:
        """Return bounded Xbox 360 structural evidence."""

        try:
            metadata = inspect_xbox360_disc(
                path
            )
        except (
            OSError,
            Xbox360FormatError,
        ):
            return PlatformDetection()

        execution = metadata.execution_id

        evidence = PlatformEvidence(
            source="xbox360-disc-structure",
            method="xdvdfs-xex2-execution-id",
            value=execution.title_id,
            strength=100,
            details={
                "filesystem": "xdvdfs",
                "executable": "default.xex",
                "media_id": execution.media_id,
                "disc_number": str(
                    execution.disc_number
                ),
                "disc_count": str(
                    execution.disc_count
                ),
            },
        )

        return PlatformDetection(
            candidates=(
                PlatformCandidate(
                    platform="xbox-360",
                    confidence=100,
                    evidence=(evidence,),
                ),
            ),
        )


class Xbox360StructuralInspector:
    """Extract Xbox 360 representation and artifact-local metadata."""

    name = "xbox360"

    def inspect(
        self,
        path: Path,
    ) -> StructuralInspectionResult | None:
        """Return Xbox 360 bounded structural metadata."""

        try:
            metadata = inspect_xbox360_disc(
                path
            )
        except (
            OSError,
            Xbox360FormatError,
        ):
            return None

        execution = metadata.execution_id

        def provenance(
            method: str,
            *,
            raw_value: str | None = None,
        ) -> LocalMetadataProvenance:
            return LocalMetadataProvenance(
                source="xbox360-xex2",
                method=method,
                raw_value=raw_value,
            )

        return StructuralInspectionResult(
            physical_representation=RepresentationIdentity(
                kind="disc-image",
                format="xbox360-xgd",
                metadata={
                    "filesystem": "xdvdfs",
                    "partition_offset": (
                        f"0x{metadata.partition_offset:X}"
                    ),
                },
            ),
            local_metadata=LocalContentMetadata(
                platform="xbox-360",
                identifiers=(
                    LocalIdentifier(
                        namespace="xbox360-title-id",
                        value=execution.title_id,
                        provenance=provenance(
                            "execution-id-title-id",
                            raw_value=execution.title_id,
                        ),
                    ),
                    LocalIdentifier(
                        namespace="xbox360-media-id",
                        value=execution.media_id,
                        provenance=provenance(
                            "execution-id-media-id",
                            raw_value=execution.media_id,
                        ),
                    ),
                ),
                executable_versions=(
                    LocalMetadataValue(
                        value=str(
                            execution.version
                        ),
                        provenance=provenance(
                            "execution-id-version",
                            raw_value=(
                                f"0x{execution.version:08X}"
                            ),
                        ),
                    ),
                ),
                disc_numbers=(
                    LocalMetadataValue(
                        value=execution.disc_number,
                        provenance=provenance(
                            "execution-id-disc-number",
                            raw_value=str(
                                execution.disc_number
                            ),
                        ),
                    ),
                ),
                media={
                    "filesystem": "xdvdfs",
                    "disc_count": str(
                        execution.disc_count
                    ),
                },
                boot={
                    "executable": "default.xex",
                },
                native_metadata={
                    "title_id": execution.title_id,
                    "media_id": execution.media_id,
                    "version": (
                        f"0x{execution.version:08X}"
                    ),
                    "base_version": (
                        f"0x{execution.base_version:08X}"
                    ),
                    "platform": str(
                        execution.platform
                    ),
                    "executable_type": str(
                        execution.executable_type
                    ),
                    "disc_number": str(
                        execution.disc_number
                    ),
                    "disc_count": str(
                        execution.disc_count
                    ),
                    "xex_sector": str(
                        metadata.xex_sector
                    ),
                    "xex_size": str(
                        metadata.xex_size
                    ),
                },
            ),
        )
