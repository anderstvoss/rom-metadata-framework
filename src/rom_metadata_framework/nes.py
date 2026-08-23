from __future__ import annotations

import hashlib
import zlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

from .capability import (
    RuntimeCapability,
    RuntimeCapabilityStatus,
)
from .content import NormalizedContentIdentity
from .identity import HashSet
from .normalization import (
    NormalizerProbe,
    NormalizerProbeStatus,
)
from .representation import RepresentationIdentity

NES_MAGIC = b"NES\x1a"
NES_HEADER_SIZE = 16
NES_TRAINER_SIZE = 512


class NesFormatError(RuntimeError):
    """Raised when an NES image cannot be normalized safely."""


@dataclass(frozen=True, slots=True)
class NesContentIdentity:
    """Normalized NES cartridge identity and representation metadata."""

    representation: str
    content: NormalizedContentIdentity
    header_metadata: Mapping[str, str] = field(
        default_factory=dict,
    )
    physical_representation: RepresentationIdentity = field(
        init=False,
    )

    def __post_init__(self) -> None:
        representation = self.representation.strip().lower()

        if representation not in {
            "nes2",
            "ines",
            "headerless",
        }:
            raise ValueError(
                f"unsupported NES representation "
                f"{representation!r}"
            )

        object.__setattr__(
            self,
            "representation",
            representation,
        )

        metadata = {
            str(key).strip(): str(value).strip()
            for key, value in self.header_metadata.items()
        }

        if any(not key for key in metadata):
            raise ValueError(
                "NES header metadata keys must not be empty"
            )

        object.__setattr__(
            self,
            "header_metadata",
            MappingProxyType(metadata),
        )
        object.__setattr__(
            self,
            "physical_representation",
            RepresentationIdentity(
                kind="cartridge-image",
                format=representation,
                metadata=metadata,
            ),
        )


class NesAdapter:
    """Normalize NES cartridge images without changing the source file."""

    name = "nes"

    def __init__(
        self,
        *,
        allow_headerless: bool = False,
    ) -> None:
        self.allow_headerless = allow_headerless

    def runtime_capability(self) -> RuntimeCapability:
        """Report built-in NES normalization runtime capability."""

        return RuntimeCapability(
            name="nes-normalization",
            status=RuntimeCapabilityStatus.READY,
        )

    def probe(self, path: Path) -> NormalizerProbe:
        """Classify whether this adapter can normalize one source."""

        path = Path(path)

        if not path.is_file():
            return NormalizerProbe(
                normalizer=self.name,
                status=NormalizerProbeStatus.UNSUPPORTED,
                reason="source is not a regular file",
            )

        with path.open("rb") as handle:
            header = handle.read(NES_HEADER_SIZE)

        if header[:4] != NES_MAGIC:
            if (
                self.allow_headerless
                and path.suffix.lower() == ".nes"
            ):
                return NormalizerProbe(
                    normalizer=self.name,
                    status=NormalizerProbeStatus.SUPPORTED,
                    reason="headerless NES explicitly enabled",
                    details={
                        "representation": "headerless",
                    },
                )

            return NormalizerProbe(
                normalizer=self.name,
                status=NormalizerProbeStatus.UNSUPPORTED,
                reason="NES header signature not present",
            )

        if len(header) != NES_HEADER_SIZE:
            return NormalizerProbe(
                normalizer=self.name,
                status=NormalizerProbeStatus.UNSAFE,
                reason="truncated NES header",
                details={
                    "representation": "headered",
                },
            )

        flags6 = header[6]
        flags7 = header[7]

        is_nes2 = (flags7 & 0x0C) == 0x08
        representation = (
            "nes2"
            if is_nes2
            else "ines"
        )

        if flags6 & 0x04:
            return NormalizerProbe(
                normalizer=self.name,
                status=NormalizerProbeStatus.UNSAFE,
                reason=(
                    "trainer-bearing NES images are not "
                    "normalized safely"
                ),
                details={
                    "representation": representation,
                    "trainer": "true",
                },
            )

        if is_nes2:
            prg_size = _nes2_rom_size(
                lsb=header[4],
                msb_nibble=header[9] & 0x0F,
                unit_size=16 * 1024,
            )
            chr_size = _nes2_rom_size(
                lsb=header[5],
                msb_nibble=(header[9] >> 4) & 0x0F,
                unit_size=8 * 1024,
            )
        else:
            prg_size = header[4] * 16 * 1024
            chr_size = header[5] * 8 * 1024

        expected_size = (
            NES_HEADER_SIZE
            + prg_size
            + chr_size
        )
        actual_size = path.stat().st_size

        details = {
            "representation": representation,
            "expected_size": str(expected_size),
            "actual_size": str(actual_size),
        }

        if actual_size < expected_size:
            return NormalizerProbe(
                normalizer=self.name,
                status=NormalizerProbeStatus.UNSAFE,
                reason="NES image is truncated",
                details=details,
            )

        if actual_size > expected_size:
            return NormalizerProbe(
                normalizer=self.name,
                status=NormalizerProbeStatus.UNSAFE,
                reason=(
                    "NES image contains trailing or "
                    "miscellaneous data"
                ),
                details=details,
            )

        return NormalizerProbe(
            normalizer=self.name,
            status=NormalizerProbeStatus.SUPPORTED,
            details=details,
        )

    def supports(self, path: Path) -> bool:
        """Return whether this adapter can safely normalize the file."""

        return self.probe(path).supported

    def identify(self, path: Path) -> NesContentIdentity:
        """Return normalized PRG+CHR identity for one NES image."""

        path = Path(path)

        if not path.is_file():
            raise NesFormatError(
                f"NES image does not exist: {path}"
            )

        with path.open("rb") as handle:
            header = handle.read(NES_HEADER_SIZE)

        if header[:4] != NES_MAGIC:
            if not self.allow_headerless:
                raise NesFormatError(
                    "headerless NES image requires "
                    "allow_headerless=True"
                )

            hashes = _hash_region(
                path,
                offset=0,
                length=path.stat().st_size,
            )

            return NesContentIdentity(
                representation="headerless",
                content=NormalizedContentIdentity(
                    kind="cartridge",
                    hashes=hashes,
                    metadata={
                        "normalization": "complete-file",
                    },
                ),
            )

        if len(header) != NES_HEADER_SIZE:
            raise NesFormatError(
                "truncated NES header"
            )

        flags6 = header[6]
        flags7 = header[7]

        is_nes2 = (flags7 & 0x0C) == 0x08
        representation = (
            "nes2"
            if is_nes2
            else "ines"
        )

        has_trainer = bool(flags6 & 0x04)

        if has_trainer:
            raise NesFormatError(
                "trainer-bearing NES images are not yet "
                "normalized because trainer semantics must "
                "remain distinct from cartridge ROM content"
            )

        if is_nes2:
            prg_size = _nes2_rom_size(
                lsb=header[4],
                msb_nibble=header[9] & 0x0F,
                unit_size=16 * 1024,
            )
            chr_size = _nes2_rom_size(
                lsb=header[5],
                msb_nibble=(header[9] >> 4) & 0x0F,
                unit_size=8 * 1024,
            )

            mapper = (
                (flags6 >> 4)
                | (flags7 & 0xF0)
                | ((header[8] & 0x0F) << 8)
            )
            submapper = (header[8] >> 4) & 0x0F
        else:
            prg_size = header[4] * 16 * 1024
            chr_size = header[5] * 8 * 1024

            mapper = (
                (flags6 >> 4)
                | (flags7 & 0xF0)
            )
            submapper = None

        content_size = prg_size + chr_size
        expected_size = (
            NES_HEADER_SIZE
            + content_size
        )
        actual_size = path.stat().st_size

        if actual_size < expected_size:
            raise NesFormatError(
                "NES image is truncated: "
                f"expected at least {expected_size} bytes, "
                f"found {actual_size}"
            )

        if actual_size > expected_size:
            raise NesFormatError(
                "NES image contains trailing or miscellaneous "
                "data that is not yet normalized safely"
            )

        hashes = _hash_region(
            path,
            offset=NES_HEADER_SIZE,
            length=content_size,
        )

        metadata = {
            "normalization": "prg+chr",
            "prg_rom_size": str(prg_size),
            "chr_rom_size": str(chr_size),
            "mapper": str(mapper),
            "trainer": "false",
        }

        header_metadata = {
            "flags6": f"{flags6:02x}",
            "flags7": f"{flags7:02x}",
            "mapper": str(mapper),
            "prg_rom_size": str(prg_size),
            "chr_rom_size": str(chr_size),
            "trainer": "false",
        }

        if submapper is not None:
            metadata["submapper"] = str(submapper)
            header_metadata["submapper"] = str(submapper)

        return NesContentIdentity(
            representation=representation,
            content=NormalizedContentIdentity(
                kind="cartridge",
                hashes=hashes,
                metadata=metadata,
            ),
            header_metadata=header_metadata,
        )


def _nes2_rom_size(
    *,
    lsb: int,
    msb_nibble: int,
    unit_size: int,
) -> int:
    """Decode one NES 2.0 PRG-ROM or CHR-ROM size field."""

    if msb_nibble != 0x0F:
        units = (
            (msb_nibble << 8)
            | lsb
        )
        return units * unit_size

    exponent = lsb >> 2
    multiplier = ((lsb & 0x03) * 2) + 1

    return (1 << exponent) * multiplier


def _hash_region(
    path: Path,
    *,
    offset: int,
    length: int,
) -> HashSet:
    """Hash exactly one byte range without creating a temporary file."""

    crc = 0
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    sha256 = hashlib.sha256()

    remaining = length

    with path.open("rb") as handle:
        handle.seek(offset)

        while remaining:
            chunk = handle.read(
                min(1024 * 1024, remaining)
            )

            if not chunk:
                raise NesFormatError(
                    "unexpected end of file while "
                    "normalizing NES content"
                )

            remaining -= len(chunk)
            crc = zlib.crc32(chunk, crc)
            md5.update(chunk)
            sha1.update(chunk)
            sha256.update(chunk)

    return HashSet(
        crc32=f"{crc & 0xffffffff:08x}",
        md5=md5.hexdigest(),
        sha1=sha1.hexdigest(),
        sha256=sha256.hexdigest(),
    )


class NesPlatformDetector:
    """Detect NES images from deterministic cartridge-header evidence."""

    name = "nes"

    def detect(self, path: Path):
        """Return NES platform evidence when a valid NES header is present."""

        from .detection import (
            PlatformCandidate,
            PlatformDetection,
            PlatformEvidence,
        )

        path = Path(path)

        if not path.is_file():
            return PlatformDetection()

        with path.open("rb") as handle:
            header = handle.read(NES_HEADER_SIZE)

        if len(header) < NES_HEADER_SIZE:
            return PlatformDetection()

        if header[:4] != NES_MAGIC:
            return PlatformDetection()

        flags7 = header[7]

        representation = (
            "nes2"
            if (flags7 & 0x0C) == 0x08
            else "ines"
        )

        evidence = PlatformEvidence(
            source="nes-header",
            method="format-signature",
            value="NES\\x1a",
            strength=100,
            details={
                "representation": representation,
            },
        )

        return PlatformDetection(
            candidates=(
                PlatformCandidate(
                    platform="nes",
                    confidence=100,
                    evidence=(evidence,),
                ),
            ),
        )
