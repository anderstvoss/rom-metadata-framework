from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .canonical import (
    CONTENT_MATCH_METHODS,
    CanonicalReleaseIdentity,
    IdentificationEvidence,
)
from .identity import RomIdentity
from .lookup import LookupIdentity
from .platforms import UnknownPlatformError, canonical_platform_name
from .provenance import CatalogueEvidence
from .resolvers import (
    MetadataResolver,
    ResolvedMetadata,
    ResolverUnavailableError,
)

DEFAULT_PLAYMATCH_API_URL = "https://playmatch.retrorealm.dev/api/v2"
DEFAULT_PLAYMATCH_TIMEOUT = 10.0

try:
    PACKAGE_VERSION = version("rom-metadata-framework")
except PackageNotFoundError:
    PACKAGE_VERSION = "unknown"

PLAYMATCH_USER_AGENT = f"rom-metadata-framework/{PACKAGE_VERSION}"


class PlaymatchError(RuntimeError):
    """Base error raised by the Playmatch resolver."""


class PlaymatchRequestError(
    PlaymatchError,
    ResolverUnavailableError,
):
    """Raised when a Playmatch request cannot be completed."""


class PlaymatchResponseError(PlaymatchError):
    """Raised when Playmatch returns an invalid success response."""


@dataclass(frozen=True, slots=True)
class PlaymatchResolver:
    """Identify and resolve ROMs through the Playmatch v2 HTTP API."""

    base_url: str = DEFAULT_PLAYMATCH_API_URL
    timeout: float = DEFAULT_PLAYMATCH_TIMEOUT

    name = "playmatch"

    def __post_init__(self) -> None:
        base_url = self.base_url.strip().rstrip("/")

        if not base_url:
            raise ValueError("Playmatch base URL must not be empty")

        if self.timeout <= 0:
            raise ValueError("Playmatch timeout must be greater than zero")

        object.__setattr__(self, "base_url", base_url)

    def identify(
        self,
        identity: RomIdentity,
    ) -> CanonicalReleaseIdentity | None:
        """Identify a release from physical-file identity."""

        return self.identify_lookup(
            LookupIdentity.from_rom_identity(identity)
        )

    def identify_lookup(
        self,
        lookup: LookupIdentity,
    ) -> CanonicalReleaseIdentity | None:
        """Identify a release from an explicit provider lookup identity."""

        payload = self._identify_payload(lookup)

        match_type = payload.get("gameMatchType")

        if match_type == "NoMatch":
            return None

        if not isinstance(match_type, str) or not match_type:
            raise PlaymatchResponseError(
                "Playmatch response is missing gameMatchType"
            )

        game = payload.get("game")

        if not isinstance(game, dict):
            raise PlaymatchResponseError(
                "matched Playmatch response is missing game"
            )

        release_name = game.get("name")
        game_id = game.get("id")

        if not isinstance(release_name, str) or not release_name.strip():
            raise PlaymatchResponseError(
                "Playmatch game is missing a valid name"
            )

        if not isinstance(game_id, str) or not game_id.strip():
            raise PlaymatchResponseError(
                "Playmatch game is missing a valid id"
            )

        provider_platform_name = self._platform_name(payload)

        if provider_platform_name is None:
            raise PlaymatchResponseError(
                "matched Playmatch response is missing platform name"
            )

        platform_name = self._canonical_platform_name(
            provider_platform_name
        )

        external_ids = self._external_ids(payload)
        external_ids["playmatch"] = game_id.strip()

        evidence = IdentificationEvidence(
            source=self.name,
            method=match_type,
            authoritative=match_type in CONTENT_MATCH_METHODS,
            value=game_id.strip(),
            details={
                "release_name": release_name.strip(),
                "platform": platform_name,
                "provider_platform": provider_platform_name,
            },
        )

        catalogue_evidence = self._catalogue_evidence(
            payload,
            lookup,
            match_type,
        )

        return CanonicalReleaseIdentity(
            release_name=release_name.strip(),
            platform=platform_name,
            title=None,
            source=self.name,
            source_id=game_id.strip(),
            external_ids=external_ids,
            evidence=(evidence,),
            catalogue_evidence=catalogue_evidence,
        )

    def resolve(self, identity: RomIdentity) -> ResolvedMetadata | None:
        """Compatibility metadata view derived from canonical identity."""

        canonical = self.identify(identity)

        if canonical is None:
            return None

        return ResolvedMetadata(
            title=canonical.release_name,
            provider=self.name,
            platform=canonical.platform,
            external_ids=canonical.external_ids,
        )

    def _identify_payload(
        self,
        lookup: LookupIdentity,
    ) -> dict[str, Any]:
        query: dict[str, str | int] = {
            "fileName": lookup.file_name,
            "fileSize": lookup.file_size,
        }

        if lookup.hashes.sha256 is not None:
            query["sha256"] = lookup.hashes.sha256

        if lookup.hashes.sha1 is not None:
            query["sha1"] = lookup.hashes.sha1

        if lookup.hashes.md5 is not None:
            query["md5"] = lookup.hashes.md5

        if lookup.hashes.crc32 is not None:
            query["crc"] = lookup.hashes.crc32

        url = (
            f"{self.base_url}/identify/relations?"
            f"{urlencode(query)}"
        )

        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": PLAYMATCH_USER_AGENT,
            },
            method="GET",
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw_payload = response.read()
        except HTTPError as exc:
            status_code = exc.code
            exc.close()
            raise PlaymatchRequestError(
                f"Playmatch returned HTTP {status_code}"
            ) from exc
        except URLError as exc:
            raise PlaymatchRequestError(
                "Playmatch request failed"
            ) from exc
        except TimeoutError as exc:
            raise PlaymatchRequestError(
                "Playmatch request timed out"
            ) from exc

        try:
            payload = json.loads(raw_payload)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise PlaymatchResponseError(
                "Playmatch returned invalid JSON"
            ) from exc

        if not isinstance(payload, dict):
            raise PlaymatchResponseError(
                "Playmatch response must be a JSON object"
            )

        return payload

    @staticmethod
    def _catalogue_evidence(
        payload: dict[str, Any],
        lookup: LookupIdentity,
        match_type: str,
    ) -> tuple[CatalogueEvidence, ...]:
        raw_files = payload.get("gameFiles", [])

        if not isinstance(raw_files, list):
            raise PlaymatchResponseError(
                "Playmatch gameFiles must be an array"
            )

        signature_group = payload.get("signatureGroup") or {}
        dat_file = payload.get("datFile") or {}
        dat_import = payload.get("datFileImport") or {}

        if not isinstance(signature_group, dict):
            raise PlaymatchResponseError(
                "Playmatch signatureGroup must be an object"
            )

        if not isinstance(dat_file, dict):
            raise PlaymatchResponseError(
                "Playmatch datFile must be an object"
            )

        if not isinstance(dat_import, dict):
            raise PlaymatchResponseError(
                "Playmatch datFileImport must be an object"
            )

        expected: str | None

        if match_type == "SHA256":
            expected = getattr(lookup.hashes, "sha256", None)
        elif match_type == "SHA1":
            expected = lookup.hashes.sha1
        elif match_type == "MD5":
            expected = lookup.hashes.md5
        elif match_type == "CRC":
            expected = lookup.hashes.crc32
        else:
            expected = None

        results: list[CatalogueEvidence] = []

        for raw_file in raw_files:
            if not isinstance(raw_file, dict):
                raise PlaymatchResponseError(
                    "Playmatch gameFiles entry must be an object"
                )

            provider_hash_key = {
                "SHA256": "sha256",
                "SHA1": "sha1",
                "MD5": "md5",
                "CRC": "crc",
            }.get(match_type)

            if provider_hash_key is not None and expected is not None:
                provider_hash = raw_file.get(provider_hash_key)

                if (
                    not isinstance(provider_hash, str)
                    or provider_hash.lower() != expected.lower()
                ):
                    continue

            hashes = {
                key: value
                for key in ("crc", "md5", "sha1", "sha256")
                if isinstance(
                    value := raw_file.get(key),
                    str,
                ) and value
            }

            details: dict[str, str] = {}

            for source_key, target_key in (
                ("id", "provider_file_id"),
                ("serial", "serial"),
                ("lastSeenDatVersion", "last_seen_dat_version"),
            ):
                value = raw_file.get(source_key)

                if value is not None:
                    details[target_key] = str(value)

            results.append(
                CatalogueEvidence(
                    source="playmatch",
                    match_method=match_type,
                    authority=signature_group.get("name"),
                    catalogue_name=dat_file.get("name"),
                    catalogue_version=dat_file.get("currentVersion"),
                    import_version=dat_import.get("version"),
                    file_status=raw_file.get("status"),
                    current_in_latest_catalogue=raw_file.get(
                        "currentInLatestDat"
                    ),
                    matched_file_name=raw_file.get("fileName"),
                    hashes=hashes,
                    details=details,
                )
            )

        return tuple(results)

    @staticmethod
    def _canonical_platform_name(
        provider_name: str,
    ) -> str:
        """Canonicalize a Playmatch platform display name when possible.

        Playmatch platform names may use catalogue-style vendor prefixes,
        such as ``Nintendo - NES`` or ``Microsoft - Xbox 360``. Try the
        complete provider name first so ordinary framework aliases retain
        precedence, then conservatively retry the suffix after one
        ``" - "`` separator.

        Unknown platforms remain provider-defined rather than being guessed.
        """

        try:
            return canonical_platform_name(
                provider_name
            )
        except UnknownPlatformError:
            pass

        separator = " - "

        if separator in provider_name:
            _, suffix = provider_name.split(
                separator,
                1,
            )

            suffix = suffix.strip()

            if suffix:
                try:
                    return canonical_platform_name(
                        suffix
                    )
                except UnknownPlatformError:
                    pass

        return provider_name

    @staticmethod
    def _platform_name(payload: dict[str, Any]) -> str | None:
        platform = payload.get("platform")

        if platform is None:
            return None

        if not isinstance(platform, dict):
            raise PlaymatchResponseError(
                "Playmatch platform must be an object"
            )

        name = platform.get("name")

        if name is None:
            return None

        if not isinstance(name, str):
            raise PlaymatchResponseError(
                "Playmatch platform name must be a string"
            )

        return name.strip() or None

    @staticmethod
    def _external_ids(payload: dict[str, Any]) -> dict[str, str]:
        raw_metadata = payload.get("externalMetadata", [])

        if not isinstance(raw_metadata, list):
            raise PlaymatchResponseError(
                "Playmatch externalMetadata must be an array"
            )

        external_ids: dict[str, str] = {}

        for entry in raw_metadata:
            if not isinstance(entry, dict):
                raise PlaymatchResponseError(
                    "Playmatch external metadata entry must be an object"
                )

            provider_name = entry.get("providerName")
            provider_id = entry.get("providerId")

            if provider_id is None:
                continue

            if not isinstance(provider_name, str) or not provider_name.strip():
                raise PlaymatchResponseError(
                    "Playmatch external metadata providerName is invalid"
                )

            if not isinstance(provider_id, str) or not provider_id.strip():
                raise PlaymatchResponseError(
                    "Playmatch external metadata providerId is invalid"
                )

            namespace = provider_name.strip().lower()

            if namespace in external_ids:
                raise PlaymatchResponseError(
                    f"duplicate Playmatch provider mapping: {namespace!r}"
                )

            external_ids[namespace] = provider_id.strip()

        return external_ids


assert isinstance(PlaymatchResolver(), MetadataResolver)
