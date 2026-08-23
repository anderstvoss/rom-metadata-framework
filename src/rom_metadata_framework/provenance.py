from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

STRONG_CONTENT_MATCH_METHODS = frozenset(
    {
        "SHA256",
        "SHA1",
        "MD5",
    }
)

CONTENT_MATCH_METHODS = STRONG_CONTENT_MATCH_METHODS | {"CRC"}


@dataclass(frozen=True, slots=True)
class CatalogueEvidence:
    """Provider-independent evidence from a ROM/disc catalogue."""

    source: str
    match_method: str

    authority: str | None = None
    catalogue_name: str | None = None
    catalogue_version: str | None = None
    import_version: str | None = None

    file_status: str | None = None
    current_in_latest_catalogue: bool | None = None

    matched_file_name: str | None = None
    hashes: Mapping[str, str] = field(default_factory=dict)
    details: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        source = self.source.strip().lower()
        method = self.match_method.strip().upper()

        if not source:
            raise ValueError("catalogue evidence source must not be empty")

        if not method:
            raise ValueError("catalogue evidence match_method must not be empty")

        object.__setattr__(self, "source", source)
        object.__setattr__(self, "match_method", method)

        for name in (
            "authority",
            "catalogue_name",
            "catalogue_version",
            "import_version",
            "file_status",
            "matched_file_name",
        ):
            value = getattr(self, name)

            if value is not None:
                object.__setattr__(
                    self,
                    name,
                    value.strip() or None,
                )

        if self.file_status is not None:
            object.__setattr__(
                self,
                "file_status",
                self.file_status.lower(),
            )

        normalized_hashes = {
            str(key).strip().lower(): str(value).strip().lower()
            for key, value in self.hashes.items()
            if str(value).strip()
        }

        normalized_details = {
            str(key).strip(): str(value).strip() for key, value in self.details.items()
        }

        if any(not key for key in normalized_hashes):
            raise ValueError("catalogue hash namespaces must not be empty")

        if any(not key for key in normalized_details):
            raise ValueError("catalogue detail keys must not be empty")

        object.__setattr__(
            self,
            "hashes",
            MappingProxyType(normalized_hashes),
        )
        object.__setattr__(
            self,
            "details",
            MappingProxyType(normalized_details),
        )

    @property
    def is_content_match(self) -> bool:
        return self.match_method in CONTENT_MATCH_METHODS

    @property
    def is_strong_content_match(self) -> bool:
        return self.match_method in STRONG_CONTENT_MATCH_METHODS

    @property
    def is_verified(self) -> bool:
        return self.file_status == "verified"
