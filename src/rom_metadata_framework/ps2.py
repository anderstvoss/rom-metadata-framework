from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import iso9660 as _iso9660
from .detection import (
    PlatformCandidate,
    PlatformDetection,
    PlatformEvidence,
)
from .iso9660 import (
    BoundedIso9660,
    Iso9660FormatError,
)

ISO_SECTOR_SIZE = _iso9660.ISO_SECTOR_SIZE
ISO_PVD_SECTOR = _iso9660.ISO_PVD_SECTOR
ISO_PVD_OFFSET = _iso9660.ISO_PVD_OFFSET
ISO_PVD_SIZE = _iso9660.ISO_PVD_SIZE
ISO_STANDARD_IDENTIFIER = (
    _iso9660.ISO_STANDARD_IDENTIFIER
)

SYSTEM_CNF_NAME = "SYSTEM.CNF"

# Preserve the historical PS2 parser bound independently of the more
# general shared ISO9660 reader default.
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

    try:
        iso = BoundedIso9660(
            path,
            max_directory_size=MAX_ROOT_DIRECTORY_SIZE,
        )

        system_cnf = iso.find(
            f"/{SYSTEM_CNF_NAME}"
        )

        if system_cnf is None or system_cnf.directory:
            raise Ps2FormatError(
                "ISO9660 root does not contain SYSTEM.CNF"
            )

        system_data = iso.read_file(
            f"/{SYSTEM_CNF_NAME}",
            max_size=MAX_SYSTEM_CNF_SIZE,
        )
    except Iso9660FormatError as exc:
        raise Ps2FormatError(str(exc)) from exc

    volume_identifier = iso.volume_identifier

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
                    platform="ps2",
                    confidence=100,
                    evidence=(evidence,),
                ),
            ),
        )


class Ps2StructuralInspector:
    """Extract PS2 representation and local metadata without normalization."""

    name = "ps2"

    def inspect(
        self,
        path: Path,
    ):
        """Return PS2 structural evidence when the source is supported."""

        from .inspection import StructuralInspectionResult
        from .local_metadata import (
            LocalContentMetadata,
            LocalIdentifier,
            LocalMetadataProvenance,
        )
        from .representation import RepresentationIdentity

        path = Path(path)

        try:
            metadata = inspect_ps2_iso(path)
        except (
            OSError,
            Ps2FormatError,
        ):
            return None

        provenance = LocalMetadataProvenance(
            source="system.cnf",
            method="boot2",
            raw_value=metadata.boot_path,
        )

        identifiers = ()

        if metadata.product_code is not None:
            identifiers = (
                LocalIdentifier(
                    namespace="ps2-product-code",
                    value=metadata.product_code,
                    provenance=provenance,
                ),
            )

        representation = RepresentationIdentity(
            kind="disc-image",
            format="iso9660",
            metadata={
                "volume_identifier": metadata.volume_identifier,
            },
        )

        local_metadata = LocalContentMetadata(
            platform="ps2",
            identifiers=identifiers,
            boot={
                "path": metadata.boot_path,
            },
            native_metadata={
                "volume_identifier": metadata.volume_identifier,
                "system_cnf_extent": str(
                    metadata.system_cnf_extent
                ),
                "system_cnf_size": str(
                    metadata.system_cnf_size
                ),
            },
        )

        return StructuralInspectionResult(
            physical_representation=representation,
            local_metadata=local_metadata,
        )
