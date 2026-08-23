from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from .backends import (
    BackendError,
    BackendExecutionError,
    BackendSpec,
    BackendStatus,
    BackendTimeoutError,
    BackendUnavailableError,
    probe_backend,
    run_backend,
)
from .capability import (
    RuntimeCapability,
    capability_from_backend_status,
)
from .content import NormalizedContentIdentity
from .local_metadata import (
    LocalContentMetadata,
    LocalIdentifier,
    LocalMetadataProvenance,
    LocalMetadataValue,
    LocalTimestamp,
)
from .normalization import (
    NormalizerProbe,
    NormalizerProbeStatus,
)
from .representation import RepresentationIdentity

XDVDFS_EXECUTABLE = "xdvdfs"

XDVDFS_MAGIC = b"MICROSOFT*XBOX*MEDIA"
XISO_DESCRIPTOR_OFFSET = 0x10000

XBE_MAGIC = b"XBEH"

XDVDFS_CHECKSUM_NAMESPACE = "xbox-xdvdfs-checksum"
XBE_SHA256_NAMESPACE = "xbox-xbe-sha256"
XBOX_TITLE_ID_NAMESPACE = "xbox-title-id"
XBOX_FORMATTED_TITLE_ID_NAMESPACE = "xbox-title-id-formatted"

_REGION_BITS = (
    (0x00000001, "north-america"),
    (0x00000002, "japan"),
    (0x00000004, "rest-of-world"),
)


class XboxResponseError(RuntimeError):
    """Raised when Xbox tooling or represented content is unusable."""


@dataclass(frozen=True, slots=True)
class XbeCertificate:
    """Metadata parsed from an original-Xbox XBE certificate."""

    title_id: str
    formatted_title_id: str
    title_name: str

    alternate_title_ids: tuple[str, ...]
    regions: tuple[str, ...]

    region_mask: int
    ratings_mask: int
    allowed_media_mask: int

    disc_number: int
    version: int

    xbe_timestamp: datetime
    certificate_timestamp: datetime


@dataclass(frozen=True, slots=True)
class XboxDiscIdentity:
    """Normalized identity and locally extracted metadata for an Xbox disc."""

    representation: str
    content: NormalizedContentIdentity
    metadata: LocalContentMetadata
    physical_representation: RepresentationIdentity


def _u32(data: bytes, offset: int) -> int:
    try:
        return struct.unpack_from("<I", data, offset)[0]
    except struct.error as exc:
        raise XboxResponseError(
            f"XBE field at offset 0x{offset:x} is truncated"
        ) from exc


def _timestamp(value: int, field_name: str) -> datetime:
    try:
        return datetime.fromtimestamp(
            value,
            tz=UTC,
        )
    except (OverflowError, OSError, ValueError) as exc:
        raise XboxResponseError(f"invalid XBE {field_name} timestamp {value}") from exc


def _format_title_id(value: int) -> str:
    raw = value.to_bytes(4, "little")
    prefix_bytes = raw[2:4][::-1]

    if all(0x30 <= byte <= 0x39 or 0x41 <= byte <= 0x5A for byte in prefix_bytes):
        prefix = prefix_bytes.decode("ascii")
    else:
        prefix = prefix_bytes.hex().upper()

    serial = int.from_bytes(
        raw[:2],
        "little",
    )

    return f"{prefix}-{serial:03d}"


def parse_xbe_certificate(data: bytes) -> XbeCertificate:
    """Parse trustworthy metadata from an XBE certificate."""

    if len(data) < 0x11C:
        raise XboxResponseError("XBE is too small to contain the required header")

    if data[:4] != XBE_MAGIC:
        raise XboxResponseError("XBE magic is not present")

    image_base = _u32(data, 0x104)
    header_size = _u32(data, 0x110)
    xbe_timestamp = _u32(data, 0x114)
    certificate_address = _u32(data, 0x118)

    certificate_offset = certificate_address - image_base

    if certificate_offset < 0:
        raise XboxResponseError("XBE certificate address precedes the image base")

    if certificate_offset + 0xB0 > len(data):
        raise XboxResponseError("XBE certificate lies outside the file")

    certificate_size = _u32(
        data,
        certificate_offset,
    )

    if certificate_size < 0xB0:
        raise XboxResponseError("XBE certificate is shorter than required fields")

    if certificate_offset != header_size:
        # Some valid XBEs use unusual certificate/header layouts.
        # The certificate pointer remains authoritative provided all
        # fields are safely contained within the file.
        pass

    certificate_timestamp = _u32(
        data,
        certificate_offset + 0x04,
    )

    title_id_value = _u32(
        data,
        certificate_offset + 0x08,
    )

    raw_title = data[certificate_offset + 0x0C : certificate_offset + 0x5C]

    try:
        title_name = raw_title.decode("utf-16le").split("\0", 1)[0].strip()
    except UnicodeDecodeError as exc:
        raise XboxResponseError("XBE title name is not valid UTF-16LE") from exc

    alternate_title_ids = []

    for offset in range(0x5C, 0x9C, 4):
        value = _u32(
            data,
            certificate_offset + offset,
        )

        if value == 0:
            continue

        alternate_title_ids.append(f"{value:08X}")

    allowed_media_mask = _u32(
        data,
        certificate_offset + 0x9C,
    )

    region_mask = _u32(
        data,
        certificate_offset + 0xA0,
    )

    ratings_mask = _u32(
        data,
        certificate_offset + 0xA4,
    )

    disc_number = _u32(
        data,
        certificate_offset + 0xA8,
    )

    version = _u32(
        data,
        certificate_offset + 0xAC,
    )

    regions = tuple(name for bit, name in _REGION_BITS if region_mask & bit)

    return XbeCertificate(
        title_id=f"{title_id_value:08X}",
        formatted_title_id=(_format_title_id(title_id_value)),
        title_name=title_name,
        alternate_title_ids=tuple(alternate_title_ids),
        regions=regions,
        region_mask=region_mask,
        ratings_mask=ratings_mask,
        allowed_media_mask=allowed_media_mask,
        disc_number=disc_number,
        version=version,
        xbe_timestamp=_timestamp(
            xbe_timestamp,
            "header",
        ),
        certificate_timestamp=_timestamp(
            certificate_timestamp,
            "certificate",
        ),
    )


class XboxAdapter:
    """Normalize original-Xbox XDVDFS disc images."""

    name = "xbox"

    def __init__(
        self,
        *,
        executable: str = XDVDFS_EXECUTABLE,
        temporary_directory: Path | None = None,
    ) -> None:
        self.backend = BackendSpec(
            name="xdvdfs",
            executable=executable,
        )
        self.temporary_directory = (
            Path(temporary_directory) if temporary_directory is not None else None
        )

    def runtime_capability(self) -> RuntimeCapability:
        health_spec = BackendSpec(
            name=self.backend.name,
            executable=self.backend.executable,
            version_args=("--version",),
        )

        status = probe_backend(health_spec)

        if status.available and status.error is None:
            status = BackendStatus(
                name=status.name,
                available=True,
                executable=status.executable,
                version=status.version,
            )

        return capability_from_backend_status(
            "xbox-normalization",
            status,
        )

    def probe(self, path: Path) -> NormalizerProbe:
        path = Path(path)

        if not path.is_file():
            return NormalizerProbe(
                normalizer=self.name,
                status=NormalizerProbeStatus.UNSUPPORTED,
                reason="source is not a regular file",
            )

        try:
            result = run_backend(
                self.backend,
                (
                    "info",
                    str(path),
                ),
            )
        except BackendUnavailableError as exc:
            return NormalizerProbe(
                normalizer=self.name,
                status=(NormalizerProbeStatus.BACKEND_UNAVAILABLE),
                reason=str(exc),
            )
        except BackendExecutionError as exc:
            # A normal xdvdfs parser rejection means that the source
            # is not a supported XDVDFS image.
            return NormalizerProbe(
                normalizer=self.name,
                status=NormalizerProbeStatus.UNSUPPORTED,
                reason=str(exc),
            )
        except BackendTimeoutError as exc:
            return NormalizerProbe(
                normalizer=self.name,
                status=NormalizerProbeStatus.BACKEND_FAILURE,
                reason=str(exc),
                details={
                    "exception": type(exc).__name__,
                },
            )
        except BackendError as exc:
            return NormalizerProbe(
                normalizer=self.name,
                status=NormalizerProbeStatus.BACKEND_FAILURE,
                reason=str(exc),
                details={
                    "exception": type(exc).__name__,
                },
            )

        output = result.stdout.lower()

        if "valid:" not in output or "true" not in output:
            return NormalizerProbe(
                normalizer=self.name,
                status=NormalizerProbeStatus.UNSUPPORTED,
                reason="xdvdfs did not report a valid image",
            )

        representation = self._representation(path)

        return NormalizerProbe(
            normalizer=self.name,
            status=NormalizerProbeStatus.SUPPORTED,
            details={
                "representation": representation,
            },
        )

    def supports(self, path: Path) -> bool:
        return self.probe(path).supported

    def identify(self, path: Path) -> XboxDiscIdentity:
        path = Path(path)

        probe = self.probe(path)

        if not probe.supported:
            raise XboxResponseError(
                f"source is not a supported Xbox image: {path.name}"
            )

        representation = self._representation(path)
        checksum = self._checksum(path)

        if (
            self.temporary_directory is not None
            and not self.temporary_directory.is_dir()
        ):
            raise FileNotFoundError(self.temporary_directory)

        with TemporaryDirectory(
            prefix="rom-metadata-framework-xbox-",
            dir=self.temporary_directory,
        ) as directory:
            xbe_path = Path(directory) / "default.xbe"

            run_backend(
                self.backend,
                (
                    "copy-out",
                    str(path),
                    "default.xbe",
                    str(xbe_path),
                ),
            )

            if not xbe_path.is_file():
                raise XboxResponseError("xdvdfs did not extract default.xbe")

            xbe_data = xbe_path.read_bytes()
            certificate = parse_xbe_certificate(xbe_data)
            xbe_sha256 = hashlib.sha256(xbe_data).hexdigest()

        metadata = self._local_metadata(
            certificate,
            representation=representation,
            xbe_sha256=xbe_sha256,
        )

        return XboxDiscIdentity(
            representation=representation,
            content=NormalizedContentIdentity(
                kind="disc",
                specialized_identifiers={
                    XDVDFS_CHECKSUM_NAMESPACE: checksum,
                    XBE_SHA256_NAMESPACE: xbe_sha256,
                    XBOX_TITLE_ID_NAMESPACE: (certificate.title_id),
                },
                metadata={
                    "normalization": "xdvdfs-content",
                    "title_id": certificate.title_id,
                    "xbe_sha256": xbe_sha256,
                },
            ),
            metadata=metadata,
            physical_representation=RepresentationIdentity(
                kind="disc-image",
                format=("xbox-xiso" if representation == "xiso" else "xbox-full-disc"),
                metadata={
                    "filesystem": "xdvdfs",
                },
            ),
        )

    def _checksum(self, path: Path) -> str:
        result = run_backend(
            self.backend,
            (
                "checksum",
                "--silent",
                str(path),
            ),
        )

        value = result.stdout.strip().split()[0].lower()

        if len(value) != 64 or any(
            character not in "0123456789abcdef" for character in value
        ):
            raise XboxResponseError("xdvdfs returned an invalid checksum")

        return value

    @staticmethod
    def _representation(path: Path) -> str:
        with Path(path).open("rb") as handle:
            handle.seek(XISO_DESCRIPTOR_OFFSET)

            if handle.read(len(XDVDFS_MAGIC)) == XDVDFS_MAGIC:
                return "xiso"

        return "full-disc"

    @staticmethod
    def _local_metadata(
        certificate: XbeCertificate,
        *,
        representation: str,
        xbe_sha256: str,
    ) -> LocalContentMetadata:
        def provenance(
            method: str,
            *,
            raw_value: str | None = None,
        ) -> LocalMetadataProvenance:
            return LocalMetadataProvenance(
                source="xbox-xbe",
                method=method,
                raw_value=raw_value,
            )

        identifiers = [
            LocalIdentifier(
                namespace=XBOX_TITLE_ID_NAMESPACE,
                value=certificate.title_id,
                provenance=provenance(
                    "certificate-title-id",
                ),
            ),
            LocalIdentifier(
                namespace=(XBOX_FORMATTED_TITLE_ID_NAMESPACE),
                value=certificate.formatted_title_id,
                provenance=provenance(
                    "certificate-title-id-formatted",
                ),
            ),
            LocalIdentifier(
                namespace=XBE_SHA256_NAMESPACE,
                value=xbe_sha256,
                provenance=provenance(
                    "default-xbe-sha256",
                ),
            ),
        ]

        identifiers.extend(
            LocalIdentifier(
                namespace="xbox-alternate-title-id",
                value=value,
                provenance=provenance(
                    "certificate-alternate-title-id",
                ),
            )
            for value in certificate.alternate_title_ids
        )

        return LocalContentMetadata(
            platform="xbox",
            titles=(
                (
                    LocalMetadataValue(
                        value=certificate.title_name,
                        provenance=provenance(
                            "certificate-title-name",
                        ),
                    ),
                )
                if certificate.title_name
                else ()
            ),
            identifiers=tuple(identifiers),
            executable_versions=(
                LocalMetadataValue(
                    value=str(certificate.version),
                    provenance=provenance(
                        "certificate-version",
                        raw_value=str(certificate.version),
                    ),
                ),
            ),
            disc_numbers=(
                LocalMetadataValue(
                    value=certificate.disc_number,
                    provenance=provenance(
                        "certificate-disc-number",
                    ),
                ),
            ),
            regions=tuple(
                LocalMetadataValue(
                    value=region,
                    provenance=provenance(
                        "certificate-region-mask",
                        raw_value=(f"0x{certificate.region_mask:08X}"),
                    ),
                )
                for region in certificate.regions
            ),
            timestamps=(
                LocalTimestamp(
                    kind="xbe-header",
                    value=certificate.xbe_timestamp,
                    provenance=provenance(
                        "xbe-header-timestamp",
                    ),
                ),
                LocalTimestamp(
                    kind="xbe-certificate",
                    value=(certificate.certificate_timestamp),
                    provenance=provenance(
                        "certificate-timestamp",
                    ),
                ),
            ),
            media={
                "representation": representation,
                "filesystem": "xdvdfs",
            },
            boot={
                "executable": "default.xbe",
            },
            native_metadata={
                "title_id": certificate.title_id,
                "formatted_title_id": (certificate.formatted_title_id),
                "region_mask": (f"0x{certificate.region_mask:08X}"),
                "ratings_mask": (f"0x{certificate.ratings_mask:08X}"),
                "allowed_media_mask": (f"0x{certificate.allowed_media_mask:08X}"),
                "disc_number": str(certificate.disc_number),
                "xbe_version": str(certificate.version),
            },
        )
