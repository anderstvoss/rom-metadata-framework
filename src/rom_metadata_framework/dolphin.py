from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from types import MappingProxyType

from .backends import (
    BackendError,
    BackendSpec,
    BackendStatus,
    BackendUnavailableError,
    probe_backend,
    run_backend,
)
from .capability import (
    RuntimeCapability,
    capability_from_backend_status,
)
from .content import NormalizedContentIdentity
from .hashing import hash_file
from .identity import HashSet
from .local_metadata import (
    LocalContentMetadata,
    LocalIdentifier,
    LocalMetadataProvenance,
    LocalMetadataValue,
)
from .normalization import (
    NormalizerProbe,
    NormalizerProbeStatus,
)
from .representation import RepresentationIdentity

DOLPHIN_EXECUTABLE = "dolphin-tool"
RETROACHIEVEMENTS_NAMESPACE = "retroachievements"

_SUPPORTED_PLATFORMS = {
    "gamecube",
    "wii",
}


class DolphinResponseError(RuntimeError):
    """Raised when dolphin-tool returns unusable disc information."""


@dataclass(frozen=True, slots=True)
class DolphinDiscIdentity:
    """Normalized identity of the disc represented by an image container."""

    platform: str
    format: str

    game_id: str
    revision: int
    content: NormalizedContentIdentity

    region: str | None = None
    country: str | None = None
    internal_name: str | None = None
    title_id: str | None = None

    container_metadata: Mapping[str, str] = field(
        default_factory=dict,
    )

    local_metadata: LocalContentMetadata = field(
        default_factory=LocalContentMetadata,
    )
    physical_representation: RepresentationIdentity = field(
        init=False,
    )

    def __post_init__(self) -> None:
        platform = self.platform.strip().lower()

        if platform not in _SUPPORTED_PLATFORMS:
            raise ValueError(f"unsupported Dolphin platform {platform!r}")

        object.__setattr__(self, "platform", platform)

        if not self.game_id.strip():
            raise ValueError("game_id must not be empty")

        object.__setattr__(
            self,
            "game_id",
            self.game_id.strip(),
        )

        if isinstance(self.revision, bool) or not isinstance(
            self.revision,
            int,
        ):
            raise TypeError("revision must be an integer")

        if self.revision < 0:
            raise ValueError("revision must not be negative")

        for name in (
            "format",
            "region",
            "country",
            "internal_name",
            "title_id",
        ):
            value = getattr(self, name)

            if value is not None:
                object.__setattr__(
                    self,
                    name,
                    str(value).strip() or None,
                )

        metadata = {
            str(key).strip(): str(value).strip()
            for key, value in self.container_metadata.items()
        }

        if any(not key for key in metadata):
            raise ValueError("container metadata keys must not be empty")

        object.__setattr__(
            self,
            "container_metadata",
            MappingProxyType(metadata),
        )

        object.__setattr__(
            self,
            "physical_representation",
            RepresentationIdentity(
                kind="disc-image",
                format=self.format or "unknown",
                metadata=metadata,
            ),
        )


class DolphinAdapter:
    """Disc normalization adapter backed by dolphin-tool."""

    name = "dolphin"

    def __init__(
        self,
        *,
        executable: str = DOLPHIN_EXECUTABLE,
        temporary_directory: Path | None = None,
    ) -> None:
        self.backend = BackendSpec(
            name=self.name,
            executable=executable,
        )
        self.temporary_directory = (
            Path(temporary_directory) if temporary_directory is not None else None
        )

    def runtime_capability(self) -> RuntimeCapability:
        # Probe the Dolphin subcommand required by this adapter.
        health_spec = BackendSpec(
            name=self.backend.name,
            executable=self.backend.executable,
            version_args=("header", "-h"),
        )

        status = probe_backend(health_spec)

        if status.available and status.error is None:
            status = BackendStatus(
                name=status.name,
                available=True,
                executable=status.executable,
            )

        return capability_from_backend_status(
            "dolphin-normalization",
            status,
        )

    def probe(self, path: Path) -> NormalizerProbe:
        """Classify Dolphin support without hiding backend failures."""

        path = Path(path)

        if not path.is_file():
            return NormalizerProbe(
                normalizer=self.name,
                status=NormalizerProbeStatus.UNSUPPORTED,
                reason="source is not a regular file",
            )

        try:
            header = self._header(path)
        except BackendUnavailableError as exc:
            return NormalizerProbe(
                normalizer=self.name,
                status=(NormalizerProbeStatus.BACKEND_UNAVAILABLE),
                reason=str(exc),
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
        except DolphinResponseError as exc:
            return NormalizerProbe(
                normalizer=self.name,
                status=NormalizerProbeStatus.BACKEND_FAILURE,
                reason=str(exc),
                details={
                    "exception": type(exc).__name__,
                },
            )

        # Dolphin 2606a returns an empty JSON object for an input
        # that is not a recognized GameCube/Wii disc.
        if not header:
            return NormalizerProbe(
                normalizer=self.name,
                status=NormalizerProbeStatus.UNSUPPORTED,
                reason="Dolphin did not recognize a disc header",
            )

        try:
            game_id = self._required_string(
                header,
                "game_id",
            )
            revision = self._required_revision(header)
        except DolphinResponseError as exc:
            return NormalizerProbe(
                normalizer=self.name,
                status=NormalizerProbeStatus.BACKEND_FAILURE,
                reason=str(exc),
                details={
                    "exception": type(exc).__name__,
                    "response": "incomplete-header",
                },
            )

        return NormalizerProbe(
            normalizer=self.name,
            status=NormalizerProbeStatus.SUPPORTED,
            details={
                "game_id": game_id,
                "revision": str(revision),
            },
        )

    def supports(self, path: Path) -> bool:
        """Return whether Dolphin can safely normalize the source."""

        return self.probe(path).supported

    def identify(self, path: Path) -> DolphinDiscIdentity:
        """Inspect and normalize a GameCube or Wii disc image."""

        path = Path(path)

        header = self._header(path)

        platform = self._platform_from_header(header)
        hashes = self._normalized_hashes(path)

        specialized_identifiers: dict[str, str] = {}

        rchash = self._hash(
            path,
            "rchash",
            allow_unsupported=True,
        )

        if rchash is not None:
            specialized_identifiers[RETROACHIEVEMENTS_NAMESPACE] = rchash

        game_id = self._required_string(
            header,
            "game_id",
        )
        revision = self._required_revision(header)
        region = self._optional_string(
            header,
            "region",
        )
        country = self._optional_string(
            header,
            "country",
        )
        internal_name = self._optional_string(
            header,
            "internal_name",
        )

        raw_title_id = header.get("title_id")
        title_id = str(raw_title_id) if raw_title_id is not None else None

        specialized_identifiers["nintendo-game-id"] = game_id

        if title_id is not None:
            specialized_identifiers["wii-title-id"] = title_id

        local_metadata = self._local_metadata(
            platform=platform,
            game_id=game_id,
            revision=revision,
            region=region,
            country=country,
            internal_name=internal_name,
            title_id=title_id,
        )

        return DolphinDiscIdentity(
            platform=platform,
            format=path.suffix.lower().lstrip(".") or "unknown",
            game_id=game_id,
            revision=revision,
            region=region,
            country=country,
            internal_name=internal_name,
            title_id=title_id,
            local_metadata=local_metadata,
            content=NormalizedContentIdentity(
                kind="disc",
                hashes=hashes,
                specialized_identifiers=specialized_identifiers,
                metadata={
                    "game_id": game_id,
                    "revision": str(revision),
                },
            ),
            container_metadata={
                key: str(header[key])
                for key in (
                    "block_size",
                    "compression_method",
                    "compression_level",
                )
                if header.get(key) is not None
            },
        )

    @staticmethod
    def _local_metadata(
        *,
        platform: str,
        game_id: str,
        revision: int,
        region: str | None,
        country: str | None,
        internal_name: str | None,
        title_id: str | None,
    ) -> LocalContentMetadata:
        provenance = LocalMetadataProvenance(
            source="dolphin",
            method="disc-header",
        )

        identifiers = [
            LocalIdentifier(
                namespace="nintendo-game-id",
                value=game_id,
                provenance=provenance,
            ),
        ]

        if title_id is not None:
            identifiers.append(
                LocalIdentifier(
                    namespace="wii-title-id",
                    value=title_id,
                    provenance=provenance,
                )
            )

        native_metadata = {
            "game_id": game_id,
            "revision": str(revision),
        }

        if region is not None:
            native_metadata["region"] = region

        if country is not None:
            native_metadata["country"] = country

        if internal_name is not None:
            native_metadata["internal_name"] = internal_name

        if title_id is not None:
            native_metadata["title_id"] = title_id

        return LocalContentMetadata(
            platform=platform,
            titles=(
                (
                    LocalMetadataValue(
                        value=internal_name,
                        provenance=provenance,
                    ),
                )
                if internal_name is not None
                else ()
            ),
            identifiers=tuple(identifiers),
            release_revisions=(
                LocalMetadataValue(
                    value=str(revision),
                    provenance=provenance,
                ),
            ),
            regions=(
                (
                    LocalMetadataValue(
                        value=region,
                        provenance=provenance,
                    ),
                )
                if region is not None
                else ()
            ),
            countries=(
                (
                    LocalMetadataValue(
                        value=country,
                        provenance=provenance,
                    ),
                )
                if country is not None
                else ()
            ),
            native_metadata=native_metadata,
        )

    def _normalized_hashes(self, path: Path) -> HashSet:
        """Hash Dolphin's reconstructed canonical plain-disc bytes."""

        if (
            self.temporary_directory is not None
            and not self.temporary_directory.is_dir()
        ):
            raise FileNotFoundError(self.temporary_directory)

        with TemporaryDirectory(
            prefix="rom-metadata-framework-dolphin-",
            dir=self.temporary_directory,
        ) as directory:
            workdir = Path(directory)
            output = workdir / "canonical.iso"
            user_directory = workdir / "dolphin-user"
            user_directory.mkdir()

            run_backend(
                self.backend,
                (
                    "convert",
                    "-u",
                    str(user_directory),
                    "-i",
                    str(path),
                    "-o",
                    str(output),
                    "-f",
                    "iso",
                ),
            )

            if not output.is_file():
                raise DolphinResponseError(
                    "dolphin-tool conversion did not produce a canonical ISO"
                )

            return hash_file(output)

    def _header(self, path: Path) -> dict[str, object]:
        result = run_backend(
            self.backend,
            (
                "header",
                "-i",
                str(path),
                "-j",
            ),
        )

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise DolphinResponseError(
                "dolphin-tool returned invalid header JSON"
            ) from exc

        if not isinstance(payload, dict):
            raise DolphinResponseError(
                "dolphin-tool header response must be a JSON object"
            )

        return payload

    def _hash(
        self,
        path: Path,
        algorithm: str,
        *,
        allow_unsupported: bool = False,
    ) -> str | None:
        result = run_backend(
            self.backend,
            (
                "verify",
                "-i",
                str(path),
                "-a",
                algorithm,
            ),
        )

        value = result.stdout.strip().lower()

        expected_lengths = {
            "crc32": 8,
            "md5": 32,
            "sha1": 40,
            "rchash": 32,
        }

        try:
            expected_length = expected_lengths[algorithm]
        except KeyError as exc:
            raise ValueError(
                f"unsupported Dolphin hash algorithm {algorithm!r}"
            ) from exc

        valid = len(value) == expected_length and all(
            character in "0123456789abcdef" for character in value
        )

        if valid:
            return value

        if allow_unsupported and (value == "" or value == "0"):
            return None

        raise DolphinResponseError(
            f"dolphin-tool returned an invalid {algorithm} value"
        )

    @staticmethod
    def _platform_from_header(
        header: Mapping[str, object],
    ) -> str:
        # Current dolphin-tool JSON exposes a title ID for Wii
        # discs but not GameCube discs.
        if header.get("title_id") is not None:
            return "wii"

        return "gamecube"

    @staticmethod
    def _required_string(
        header: Mapping[str, object],
        field_name: str,
    ) -> str:
        value = header.get(field_name)

        if not isinstance(value, str) or not value.strip():
            raise DolphinResponseError(f"dolphin-tool header is missing {field_name}")

        return value.strip()

    @staticmethod
    def _optional_string(
        header: Mapping[str, object],
        field_name: str,
    ) -> str | None:
        value = header.get(field_name)

        if value is None:
            return None

        if not isinstance(value, str):
            raise DolphinResponseError(
                f"dolphin-tool header field {field_name} must be a string"
            )

        return value.strip() or None

    @staticmethod
    def _required_revision(
        header: Mapping[str, object],
    ) -> int:
        value = header.get("revision")

        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise DolphinResponseError(
                "dolphin-tool header contains an invalid revision"
            )

        return value


class DolphinPlatformDetector:
    """Detect GameCube/Wii by parsing the represented disc with Dolphin."""

    name = "dolphin"

    def __init__(
        self,
        *,
        executable: str = DOLPHIN_EXECUTABLE,
    ) -> None:
        self.adapter = DolphinAdapter(
            executable=executable,
        )

    def detect(self, path: Path):
        """Return platform evidence from Dolphin disc-header parsing."""

        from .backends import BackendError
        from .detection import (
            PlatformCandidate,
            PlatformDetection,
            PlatformEvidence,
        )

        path = Path(path)

        if not path.is_file():
            return PlatformDetection()

        try:
            header = self.adapter._header(path)
            platform = self.adapter._platform_from_header(header)
        except (
            BackendError,
            DolphinResponseError,
        ):
            return PlatformDetection()

        game_id = header.get("game_id")

        if not isinstance(game_id, str) or not game_id.strip():
            return PlatformDetection()

        details = {
            "game_id": game_id.strip(),
        }

        revision = header.get("revision")
        region = header.get("region")
        title_id = header.get("title_id")

        if revision is not None:
            details["revision"] = str(revision)

        if region is not None:
            details["region"] = str(region)

        if title_id is not None:
            details["title_id"] = str(title_id)

        evidence = PlatformEvidence(
            source="dolphin",
            method="disc-header",
            value=game_id.strip(),
            strength=100,
            details=details,
        )

        return PlatformDetection(
            candidates=(
                PlatformCandidate(
                    platform=platform,
                    confidence=100,
                    evidence=(evidence,),
                ),
            ),
        )
