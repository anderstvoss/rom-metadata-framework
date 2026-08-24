from __future__ import annotations

import xml.etree.ElementTree as ET
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
from .switch_container import (
    SwitchContainerEntry,
    SwitchContainerError,
    SwitchContainerTable,
    parse_pfs0,
    parse_xci,
    read_entry_range,
)

SWITCH_PLATFORM = "nintendo-switch"

MAX_CNMT_XML_SIZE = 1024 * 1024

CNMT_XML_SUFFIX = ".cnmt.xml"
CNMT_NCA_SUFFIX = ".cnmt.nca"
NCA_SUFFIX = ".nca"
TICKET_SUFFIX = ".tik"
CERT_SUFFIX = ".cert"


class NintendoSwitchFormatError(RuntimeError):
    """Raised when Switch structural metadata is invalid."""


@dataclass(frozen=True, slots=True)
class SwitchApplicationMetadata:
    """Optional plaintext application metadata from CNMT XML."""

    application_id: str
    version: int
    required_system_version: int | None
    patch_id: str | None


@dataclass(frozen=True, slots=True)
class SwitchRightsMetadata:
    """Rights evidence derived from a ticket filename."""

    rights_id: str
    rights_title_id: str


@dataclass(frozen=True, slots=True)
class SwitchPackageMetadata:
    """Bounded structural metadata from a Switch package."""

    representation: str
    container_format: str
    entry_count: int
    nca_count: int
    cnmt_nca_count: int
    application: SwitchApplicationMetadata | None
    rights: tuple[SwitchRightsMetadata, ...]


def _normalize_hex_identifier(
    value: str,
    *,
    digits: int,
    label: str,
) -> str:
    normalized = value.strip()

    if normalized.lower().startswith("0x"):
        normalized = normalized[2:]

    if len(normalized) != digits:
        raise NintendoSwitchFormatError(
            f"{label} must contain {digits} hexadecimal digits"
        )

    try:
        int(normalized, 16)
    except ValueError as exc:
        raise NintendoSwitchFormatError(
            f"{label} is not hexadecimal"
        ) from exc

    return normalized.upper()


def _ticket_metadata(
    entries: tuple[SwitchContainerEntry, ...],
) -> tuple[SwitchRightsMetadata, ...]:
    result = []

    for entry in entries:
        if not entry.name.lower().endswith(
            TICKET_SUFFIX
        ):
            continue

        stem = entry.name[
            : -len(TICKET_SUFFIX)
        ]

        if len(stem) != 32:
            continue

        try:
            rights_id = _normalize_hex_identifier(
                stem,
                digits=32,
                label="Switch rights ID",
            )
        except NintendoSwitchFormatError:
            continue

        result.append(
            SwitchRightsMetadata(
                rights_id=rights_id,
                rights_title_id=rights_id[:16],
            )
        )

    return tuple(result)


def _xml_local_name(
    tag: str,
) -> str:
    return tag.rsplit("}", 1)[-1]


def _direct_child_text(
    root: ET.Element,
    name: str,
) -> str | None:
    matches = [
        child
        for child in root
        if _xml_local_name(child.tag) == name
    ]

    if len(matches) > 1:
        raise NintendoSwitchFormatError(
            f"CNMT XML contains duplicate root {name}"
        )

    if not matches:
        return None

    text = (
        matches[0].text or ""
    ).strip()

    if not text:
        raise NintendoSwitchFormatError(
            f"CNMT XML root {name} is empty"
        )

    return text


def _parse_optional_integer(
    value: str | None,
    *,
    label: str,
) -> int | None:
    if value is None:
        return None

    try:
        result = int(
            value,
            0,
        )
    except ValueError as exc:
        raise NintendoSwitchFormatError(
            f"{label} is not an integer"
        ) from exc

    if result < 0:
        raise NintendoSwitchFormatError(
            f"{label} must not be negative"
        )

    return result


def _parse_cnmt_xml(
    data: bytes,
) -> SwitchApplicationMetadata | None:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise NintendoSwitchFormatError(
            "CNMT XML is not valid XML"
        ) from exc

    if _xml_local_name(root.tag) != "ContentMeta":
        raise NintendoSwitchFormatError(
            "CNMT XML root is not ContentMeta"
        )

    meta_type = _direct_child_text(
        root,
        "Type",
    )

    if meta_type != "Application":
        return None

    application_id_raw = _direct_child_text(
        root,
        "Id",
    )

    if application_id_raw is None:
        raise NintendoSwitchFormatError(
            "Application CNMT XML is missing root Id"
        )

    application_id = _normalize_hex_identifier(
        application_id_raw,
        digits=16,
        label="Switch application ID",
    )

    version_raw = _direct_child_text(
        root,
        "Version",
    )

    if version_raw is None:
        raise NintendoSwitchFormatError(
            "Application CNMT XML is missing Version"
        )

    version = _parse_optional_integer(
        version_raw,
        label="Switch application version",
    )

    assert version is not None

    required_system_version = _parse_optional_integer(
        _direct_child_text(
            root,
            "RequiredSystemVersion",
        ),
        label="Switch required system version",
    )

    patch_raw = _direct_child_text(
        root,
        "PatchId",
    )

    patch_id = (
        _normalize_hex_identifier(
            patch_raw,
            digits=16,
            label="Switch patch ID",
        )
        if patch_raw is not None
        else None
    )

    return SwitchApplicationMetadata(
        application_id=application_id,
        version=version,
        required_system_version=(
            required_system_version
        ),
        patch_id=patch_id,
    )


def _application_from_pfs0(
    path: Path,
    table: SwitchContainerTable,
) -> SwitchApplicationMetadata | None:
    xml_entries = tuple(
        entry
        for entry in table.entries
        if entry.name.lower().endswith(
            CNMT_XML_SUFFIX
        )
    )

    if not xml_entries:
        return None

    applications = []

    for entry in xml_entries:
        if entry.size > MAX_CNMT_XML_SIZE:
            raise NintendoSwitchFormatError(
                "CNMT XML exceeds bounded size limit"
            )

        data = read_entry_range(
            path,
            entry,
            offset=0,
            size=entry.size,
            max_size=MAX_CNMT_XML_SIZE,
        )

        application = _parse_cnmt_xml(
            data
        )

        if application is not None:
            applications.append(
                application
            )

    if len(applications) > 1:
        identifiers = {
            item.application_id
            for item in applications
        }

        if len(identifiers) > 1:
            raise NintendoSwitchFormatError(
                "NSP contains conflicting Application CNMT XML IDs"
            )

        raise NintendoSwitchFormatError(
            "NSP contains duplicate Application CNMT XML metadata"
        )

    if not applications:
        return None

    return applications[0]


def _switch_specific_entries(
    table: SwitchContainerTable,
) -> tuple[int, int]:
    nca_count = sum(
        entry.name.lower().endswith(
            NCA_SUFFIX
        )
        for entry in table.entries
    )

    cnmt_nca_count = sum(
        entry.name.lower().endswith(
            CNMT_NCA_SUFFIX
        )
        for entry in table.entries
    )

    return (
        nca_count,
        cnmt_nca_count,
    )


def inspect_switch_package(
    path: Path,
) -> SwitchPackageMetadata:
    """Inspect bounded plaintext Switch container metadata."""

    path = Path(path)

    try:
        with path.open("rb") as handle:
            prefix = handle.read(4)

        if prefix == b"PFS0":
            table = parse_pfs0(path)

            (
                nca_count,
                cnmt_nca_count,
            ) = _switch_specific_entries(
                table
            )

            if (
                nca_count == 0
                or cnmt_nca_count == 0
            ):
                raise NintendoSwitchFormatError(
                    "PFS0 lacks Switch NCA/CNMT structure"
                )

            application = _application_from_pfs0(
                path,
                table,
            )

            rights = _ticket_metadata(
                table.entries
            )

            return SwitchPackageMetadata(
                representation="package",
                container_format="pfs0",
                entry_count=len(
                    table.entries
                ),
                nca_count=nca_count,
                cnmt_nca_count=(
                    cnmt_nca_count
                ),
                application=application,
                rights=rights,
            )

        structure = parse_xci(path)

        (
            nca_count,
            cnmt_nca_count,
        ) = _switch_specific_entries(
            structure.secure
        )

        if (
            nca_count == 0
            or cnmt_nca_count == 0
        ):
            raise NintendoSwitchFormatError(
                "XCI secure partition lacks Switch "
                "NCA/CNMT structure"
            )

        rights = _ticket_metadata(
            structure.secure.entries
        )

        return SwitchPackageMetadata(
            representation="game-card-image",
            container_format="xci",
            entry_count=len(
                structure.secure.entries
            ),
            nca_count=nca_count,
            cnmt_nca_count=cnmt_nca_count,
            application=None,
            rights=rights,
        )

    except OSError as exc:
        raise NintendoSwitchFormatError(
            str(exc)
        ) from exc
    except SwitchContainerError as exc:
        raise NintendoSwitchFormatError(
            str(exc)
        ) from exc


class NintendoSwitchPlatformDetector:
    """Detect Nintendo Switch XCI and NSP containers."""

    name = "switch"

    def detect(
        self,
        path: Path,
    ) -> PlatformDetection:
        try:
            metadata = inspect_switch_package(
                path
            )
        except NintendoSwitchFormatError:
            return PlatformDetection()

        details = {
            "representation": metadata.representation,
            "container": metadata.container_format,
            "nca_count": str(
                metadata.nca_count
            ),
            "cnmt_nca_count": str(
                metadata.cnmt_nca_count
            ),
        }

        if metadata.application is not None:
            details[
                "application_id"
            ] = (
                metadata.application.application_id
            )

        evidence = PlatformEvidence(
            source="switch-container-structure",
            method=(
                f"{metadata.container_format}-"
                "nca-cnmt"
            ),
            value=(
                metadata.application.application_id
                if metadata.application is not None
                else metadata.container_format
            ),
            strength=100,
            details=details,
        )

        return PlatformDetection(
            candidates=(
                PlatformCandidate(
                    platform=SWITCH_PLATFORM,
                    confidence=100,
                    evidence=(evidence,),
                ),
            )
        )


class NintendoSwitchStructuralInspector:
    """Preserve bounded plaintext Switch package metadata."""

    name = "switch"

    def inspect(
        self,
        path: Path,
    ) -> StructuralInspectionResult | None:
        try:
            metadata = inspect_switch_package(
                path
            )
        except NintendoSwitchFormatError:
            return None

        identifiers = []

        application = metadata.application

        if application is not None:
            identifiers.append(
                LocalIdentifier(
                    namespace="switch-application-id",
                    value=application.application_id,
                    provenance=LocalMetadataProvenance(
                        source="cnmt-xml",
                        method="root-application-id",
                    ),
                )
            )

        for rights in metadata.rights:
            identifiers.append(
                LocalIdentifier(
                    namespace="switch-rights-id",
                    value=rights.rights_id,
                    provenance=LocalMetadataProvenance(
                        source="ticket-filename",
                        method="rights-id",
                    ),
                )
            )
            identifiers.append(
                LocalIdentifier(
                    namespace="switch-rights-title-id",
                    value=rights.rights_title_id,
                    provenance=LocalMetadataProvenance(
                        source="ticket-filename",
                        method="rights-title-id",
                    ),
                )
            )

        software_versions = []

        if application is not None:
            software_versions.append(
                LocalMetadataValue(
                    value=str(
                        application.version
                    ),
                    provenance=(
                        LocalMetadataProvenance(
                            source="cnmt-xml",
                            method="root-version",
                        )
                    ),
                )
            )

        native_metadata = {
            "container_format": (
                metadata.container_format
            ),
            "entry_count": str(
                metadata.entry_count
            ),
            "nca_count": str(
                metadata.nca_count
            ),
            "cnmt_nca_count": str(
                metadata.cnmt_nca_count
            ),
        }

        if application is not None:
            if (
                application.required_system_version
                is not None
            ):
                native_metadata[
                    "required_system_version"
                ] = str(
                    application.required_system_version
                )

            if application.patch_id is not None:
                native_metadata[
                    "patch_id"
                ] = application.patch_id

        return StructuralInspectionResult(
            physical_representation=(
                RepresentationIdentity(
                    kind=metadata.representation,
                    format=metadata.container_format,
                    metadata={
                        "container": (
                            metadata.container_format
                        ),
                    },
                )
            ),
            local_metadata=LocalContentMetadata(
                platform=SWITCH_PLATFORM,
                identifiers=tuple(
                    identifiers
                ),
                software_versions=tuple(
                    software_versions
                ),
                media={
                    "representation": (
                        metadata.representation
                    ),
                    "container": (
                        metadata.container_format
                    ),
                },
                native_metadata=(
                    native_metadata
                ),
            ),
        )
