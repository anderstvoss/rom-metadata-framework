from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from pathlib import Path

from .detection import (
    PlatformCandidate,
    PlatformDetection,
    PlatformEvidence,
)
from .inspection import StructuralInspectionResult
from .iso9660 import (
    BoundedIso9660,
    Iso9660FormatError,
)
from .local_metadata import (
    LocalContentMetadata,
    LocalIdentifier,
    LocalMetadataProvenance,
    LocalMetadataValue,
)
from .representation import RepresentationIdentity

PS3_DISC_SFB_PATH = "/PS3_DISC.SFB"
PS3_PARAM_SFO_PATH = "/PS3_GAME/PARAM.SFO"
PS3_EBOOT_PATH = "/PS3_GAME/USRDIR/EBOOT.BIN"

MAX_PS3_SFB_SIZE = 256 * 1024
MAX_PS3_SFO_SIZE = 256 * 1024

_SFB_MAGIC = b".SFB"
_SFO_MAGIC = b"\x00PSF"

_SFO_FORMAT_BINARY = 0x0004
_SFO_FORMAT_STRING = 0x0204
_SFO_FORMAT_INTEGER = 0x0404

_PS3_TITLE_ID_RE = re.compile(
    r"^[A-Z]{4}\d{5}$"
)


class Ps3FormatError(RuntimeError):
    """Raised when PS3 disc metadata cannot be parsed safely."""


@dataclass(frozen=True, slots=True)
class Ps3DiscMetadata:
    """Trustworthy structural metadata extracted from a PS3 disc image."""

    volume_identifier: str
    title_id: str
    title: str | None
    category: str
    app_version: str | None
    version: str | None
    system_version: str | None
    bootable: int | None
    sfb_title_id: str
    param_sfo_extent: int
    param_sfo_size: int
    disc_sfb_extent: int
    disc_sfb_size: int
    eboot_present: bool


def _parse_sfb_title_id(data: bytes) -> str:
    if len(data) < 0x60:
        raise Ps3FormatError(
            "PS3_DISC.SFB is shorter than required fields"
        )

    if data[:4] != _SFB_MAGIC:
        raise Ps3FormatError(
            "PS3_DISC.SFB magic is invalid"
        )

    record_offset = 0x20

    while record_offset + 0x20 <= len(data):
        record = data[
            record_offset : record_offset + 0x20
        ]

        raw_key = record[:16]

        try:
            key = (
                raw_key.split(b"\x00", 1)[0]
                .decode("ascii", errors="strict")
            )
        except UnicodeDecodeError as exc:
            raise Ps3FormatError(
                "PS3_DISC.SFB key is not valid ASCII"
            ) from exc

        if not key:
            break

        value_offset = int.from_bytes(
            record[16:20],
            "big",
        )
        value_size = int.from_bytes(
            record[20:24],
            "big",
        )

        if value_offset > len(data):
            raise Ps3FormatError(
                f"PS3_DISC.SFB {key} offset lies beyond file"
            )

        if value_size > len(data) - value_offset:
            raise Ps3FormatError(
                f"PS3_DISC.SFB {key} value extends beyond file"
            )

        if key == "TITLE_ID":
            raw_value = data[
                value_offset : value_offset + value_size
            ]

            try:
                value = (
                    raw_value.split(b"\x00", 1)[0]
                    .decode("ascii", errors="strict")
                    .strip()
                )
            except UnicodeDecodeError as exc:
                raise Ps3FormatError(
                    "PS3_DISC.SFB TITLE_ID is not valid ASCII"
                ) from exc

            normalized = value.replace("-", "")

            if not _PS3_TITLE_ID_RE.fullmatch(
                normalized
            ):
                raise Ps3FormatError(
                    "PS3_DISC.SFB TITLE_ID is invalid"
                )

            return normalized

        record_offset += 0x20

    raise Ps3FormatError(
        "PS3_DISC.SFB does not contain TITLE_ID"
    )


def _parse_sfo(
    data: bytes,
) -> dict[str, str | int | bytes]:
    if len(data) < 20:
        raise Ps3FormatError(
            "PARAM.SFO header is truncated"
        )

    if data[:4] != _SFO_MAGIC:
        raise Ps3FormatError(
            "PARAM.SFO magic is invalid"
        )

    (
        _version,
        keys_offset,
        values_offset,
        count,
    ) = struct.unpack_from(
        "<4I",
        data,
        4,
    )

    if count > 4096:
        raise Ps3FormatError(
            "PARAM.SFO entry count exceeds bounded limit"
        )

    table_end = 20 + count * 16

    if table_end > len(data):
        raise Ps3FormatError(
            "PARAM.SFO index table is truncated"
        )

    if (
        keys_offset < table_end
        or keys_offset > len(data)
        or values_offset < keys_offset
        or values_offset > len(data)
    ):
        raise Ps3FormatError(
            "PARAM.SFO table offsets are invalid"
        )

    result: dict[str, str | int | bytes] = {}

    for index in range(count):
        offset = 20 + index * 16

        (
            key_relative,
            value_format,
            used_length,
            maximum_length,
            value_relative,
        ) = struct.unpack_from(
            "<HHIII",
            data,
            offset,
        )

        if used_length > maximum_length:
            raise Ps3FormatError(
                "PARAM.SFO used length exceeds maximum length"
            )

        key_start = keys_offset + key_relative

        if key_start >= values_offset:
            raise Ps3FormatError(
                "PARAM.SFO key offset is invalid"
            )

        key_end = data.find(
            b"\x00",
            key_start,
            values_offset,
        )

        if key_end < 0:
            raise Ps3FormatError(
                "PARAM.SFO key is not terminated"
            )

        try:
            key = data[
                key_start:key_end
            ].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise Ps3FormatError(
                "PARAM.SFO key is not valid UTF-8"
            ) from exc

        value_start = values_offset + value_relative
        value_end = value_start + used_length

        if value_start > len(data) or value_end > len(data):
            raise Ps3FormatError(
                f"PARAM.SFO value lies beyond file: {key}"
            )

        raw = data[value_start:value_end]

        if value_format == _SFO_FORMAT_STRING:
            try:
                value: str | int | bytes = (
                    raw.rstrip(b"\x00")
                    .decode("utf-8")
                )
            except UnicodeDecodeError as exc:
                raise Ps3FormatError(
                    f"PARAM.SFO string is not valid UTF-8: {key}"
                ) from exc

        elif value_format == _SFO_FORMAT_INTEGER:
            if used_length != 4:
                raise Ps3FormatError(
                    f"PARAM.SFO integer has invalid size: {key}"
                )

            value = int.from_bytes(
                raw,
                "little",
            )

        elif value_format == _SFO_FORMAT_BINARY:
            value = raw

        else:
            raise Ps3FormatError(
                f"PARAM.SFO value format is unsupported: {key}"
            )

        if key in result:
            raise Ps3FormatError(
                f"PARAM.SFO contains duplicate key: {key}"
            )

        result[key] = value

    return result


def _optional_string(
    values: dict[str, str | int | bytes],
    key: str,
) -> str | None:
    value = values.get(key)

    if value is None:
        return None

    if not isinstance(value, str):
        raise Ps3FormatError(
            f"PARAM.SFO {key} is not a string"
        )

    normalized = value.strip()

    return normalized or None


def _optional_integer(
    values: dict[str, str | int | bytes],
    key: str,
) -> int | None:
    value = values.get(key)

    if value is None:
        return None

    if isinstance(value, bool) or not isinstance(
        value,
        int,
    ):
        raise Ps3FormatError(
            f"PARAM.SFO {key} is not an integer"
        )

    return value


def inspect_ps3_iso(
    path: Path,
) -> Ps3DiscMetadata:
    """Parse bounded PS3 disc metadata from a readable ISO9660 image."""

    path = Path(path)

    try:
        iso = BoundedIso9660(path)

        sfb_entry = iso.find(
            PS3_DISC_SFB_PATH
        )
        sfo_entry = iso.find(
            PS3_PARAM_SFO_PATH
        )

        if (
            sfb_entry is None
            or sfb_entry.directory
        ):
            raise Ps3FormatError(
                "PS3 disc does not contain PS3_DISC.SFB"
            )

        if (
            sfo_entry is None
            or sfo_entry.directory
        ):
            raise Ps3FormatError(
                "PS3 disc does not contain PS3_GAME/PARAM.SFO"
            )

        sfb = iso.read_file(
            PS3_DISC_SFB_PATH,
            max_size=MAX_PS3_SFB_SIZE,
        )
        sfo = iso.read_file(
            PS3_PARAM_SFO_PATH,
            max_size=MAX_PS3_SFO_SIZE,
        )

        eboot = iso.find(
            PS3_EBOOT_PATH
        )

    except Iso9660FormatError as exc:
        raise Ps3FormatError(str(exc)) from exc

    sfb_title_id = _parse_sfb_title_id(sfb)
    values = _parse_sfo(sfo)

    category = _optional_string(
        values,
        "CATEGORY",
    )

    if category != "DG":
        raise Ps3FormatError(
            "PARAM.SFO CATEGORY is not a PS3 disc game"
        )

    title_id = _optional_string(
        values,
        "TITLE_ID",
    )

    if (
        title_id is None
        or not _PS3_TITLE_ID_RE.fullmatch(title_id)
    ):
        raise Ps3FormatError(
            "PARAM.SFO TITLE_ID is invalid"
        )

    if title_id != sfb_title_id:
        raise Ps3FormatError(
            "PS3_DISC.SFB and PARAM.SFO TITLE_ID values disagree"
        )

    return Ps3DiscMetadata(
        volume_identifier=iso.volume_identifier,
        title_id=title_id,
        title=_optional_string(
            values,
            "TITLE",
        ),
        category=category,
        app_version=_optional_string(
            values,
            "APP_VER",
        ),
        version=_optional_string(
            values,
            "VERSION",
        ),
        system_version=_optional_string(
            values,
            "PS3_SYSTEM_VER",
        ),
        bootable=_optional_integer(
            values,
            "BOOTABLE",
        ),
        sfb_title_id=sfb_title_id,
        param_sfo_extent=sfo_entry.extent,
        param_sfo_size=sfo_entry.size,
        disc_sfb_extent=sfb_entry.extent,
        disc_sfb_size=sfb_entry.size,
        eboot_present=(
            eboot is not None
            and not eboot.directory
        ),
    )


class Ps3PlatformDetector:
    """Detect readable PS3 disc images from independent disc metadata."""

    name = "ps3"

    def detect(
        self,
        path: Path,
    ) -> PlatformDetection:
        """Return PS3 evidence from bounded SFB/SFO inspection."""

        try:
            metadata = inspect_ps3_iso(path)
        except (
            OSError,
            Ps3FormatError,
        ):
            return PlatformDetection()

        evidence = PlatformEvidence(
            source="ps3-disc-structure",
            method="sfb-param-sfo",
            value=metadata.title_id,
            strength=100,
            details={
                "filesystem": "iso9660",
                "volume_identifier": (
                    metadata.volume_identifier
                ),
                "title_id": metadata.title_id,
                "category": metadata.category,
                "eboot_present": str(
                    metadata.eboot_present
                ).lower(),
            },
        )

        return PlatformDetection(
            candidates=(
                PlatformCandidate(
                    platform="playstation-3",
                    confidence=100,
                    evidence=(evidence,),
                ),
            ),
        )


class Ps3StructuralInspector:
    """Extract PS3 representation and artifact-local metadata."""

    name = "ps3"

    def inspect(
        self,
        path: Path,
    ) -> StructuralInspectionResult | None:
        """Return PS3 structural evidence for readable disc images."""

        try:
            metadata = inspect_ps3_iso(path)
        except (
            OSError,
            Ps3FormatError,
        ):
            return None

        title_id_provenance = LocalMetadataProvenance(
            source="param.sfo",
            method="title-id",
            raw_value=metadata.title_id,
            details={
                "cross_checked_with": "ps3_disc.sfb",
            },
        )

        values = []

        if metadata.title is not None:
            values.append(
                LocalMetadataValue(
                    value=metadata.title,
                    provenance=LocalMetadataProvenance(
                        source="param.sfo",
                        method="title",
                        raw_value=metadata.title,
                    ),
                )
            )

        software_versions = []

        if metadata.app_version is not None:
            software_versions.append(
                LocalMetadataValue(
                    value=metadata.app_version,
                    provenance=LocalMetadataProvenance(
                        source="param.sfo",
                        method="app-ver",
                        raw_value=metadata.app_version,
                    ),
                )
            )

        native_metadata = {
            "category": metadata.category,
            "title_id": metadata.title_id,
            "sfb_title_id": metadata.sfb_title_id,
            "param_sfo_extent": str(
                metadata.param_sfo_extent
            ),
            "param_sfo_size": str(
                metadata.param_sfo_size
            ),
            "disc_sfb_extent": str(
                metadata.disc_sfb_extent
            ),
            "disc_sfb_size": str(
                metadata.disc_sfb_size
            ),
            "eboot_present": str(
                metadata.eboot_present
            ).lower(),
        }

        if metadata.version is not None:
            native_metadata["version"] = (
                metadata.version
            )

        if metadata.system_version is not None:
            native_metadata["ps3_system_version"] = (
                metadata.system_version
            )

        if metadata.bootable is not None:
            native_metadata["bootable"] = str(
                metadata.bootable
            )

        return StructuralInspectionResult(
            physical_representation=RepresentationIdentity(
                kind="disc-image",
                format="iso9660",
                metadata={
                    "volume_identifier": (
                        metadata.volume_identifier
                    ),
                },
            ),
            local_metadata=LocalContentMetadata(
                platform="playstation-3",
                titles=tuple(values),
                identifiers=(
                    LocalIdentifier(
                        namespace="ps3-title-id",
                        value=metadata.title_id,
                        provenance=title_id_provenance,
                    ),
                ),
                software_versions=tuple(
                    software_versions
                ),
                media={
                    "volume_identifier": (
                        metadata.volume_identifier
                    ),
                },
                boot={
                    "eboot_present": str(
                        metadata.eboot_present
                    ).lower(),
                },
                native_metadata=native_metadata,
            ),
        )
