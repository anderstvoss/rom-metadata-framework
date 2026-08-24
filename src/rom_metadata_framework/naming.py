from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .canonical import CanonicalReleaseIdentity
from .identification import (
    IdentificationResult,
    IdentificationVerification,
)

_INVALID_FILENAME_CHARACTERS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename_component(value: str) -> str:
    """Return a conservative cross-platform filename component."""

    value = _INVALID_FILENAME_CHARACTERS.sub("_", value)
    value = re.sub(r"\s+", " ", value)
    value = value.strip().rstrip(".")

    if not value:
        raise ValueError("canonical filename component is empty")

    return value


_PRIMARY_IDENTIFIER_NAMESPACES = {
    "gc": "nintendo-game-id",
    "wii": "nintendo-game-id",
    "ps2": "ps2-product-code",
    "ps3": "ps3-title-id",
    "xbox": "xbox-title-id",
    "xbox360": "xbox360-title-id",
    "switch": "switch-application-id",
}


@dataclass(frozen=True, slots=True)
class NamingInput:
    """Selected structured evidence used to construct one filename.

    The input deliberately contains only fields with naming semantics.
    It is not a replacement for canonical release identity or complete
    artifact-local metadata.
    """

    title: str
    title_is_structured: bool = False
    platform: str | None = None
    primary_identifier: str | None = None
    region: str | None = None
    revision: str | None = None
    disc_number: int | None = None
    disc_total: int | None = None
    media_qualifier: str | None = None

    def __post_init__(self) -> None:
        title = self.title.strip()

        if not title:
            raise ValueError("naming title must not be empty")

        object.__setattr__(self, "title", title)

        for name in (
            "platform",
            "primary_identifier",
            "region",
            "revision",
            "media_qualifier",
        ):
            value = getattr(self, name)

            if value is not None:
                object.__setattr__(
                    self,
                    name,
                    str(value).strip() or None,
                )

        number = self.disc_number
        total = self.disc_total

        for name, value in (
            ("disc_number", number),
            ("disc_total", total),
        ):
            if (
                value is not None
                and (
                    isinstance(value, bool)
                    or not isinstance(value, int)
                    or value < 1
                )
            ):
                raise ValueError(
                    f"{name} must be a positive integer"
                )

        if (number is None) != (total is None):
            raise ValueError(
                "disc_number and disc_total must be supplied together"
            )

        if (
            number is not None
            and total is not None
            and number > total
        ):
            raise ValueError(
                "disc_number must not exceed disc_total"
            )


def _first_local_value(
    metadata: object | None,
    field: str,
) -> object | None:
    if metadata is None:
        return None

    values = getattr(metadata, field, ())

    if not values:
        return None

    return getattr(values[0], "value", None)


def _primary_identifier(
    result: IdentificationResult,
    *,
    platform: str | None,
) -> str | None:
    if platform is None or result.local_metadata is None:
        return None

    namespace = _PRIMARY_IDENTIFIER_NAMESPACES.get(platform)

    if namespace is None:
        return None

    for identifier in result.local_metadata.identifiers:
        if identifier.namespace == namespace:
            return identifier.value

    return None


def naming_input_from_identification(
    result: IdentificationResult,
) -> NamingInput:
    """Select naming-safe structured evidence from identification."""

    canonical = result.canonical_match

    if canonical is None:
        raise ValueError(
            "canonical release identity is required for canonical naming"
        )

    structured_title = canonical.title is not None
    title = canonical.title or canonical.release_name

    platform = canonical.platform
    metadata = result.local_metadata

    local_platform_agrees = bool(
        metadata is not None
        and metadata.platform == platform
    )

    identifier = (
        _primary_identifier(
            result,
            platform=platform,
        )
        if local_platform_agrees
        else None
    )

    region = None
    revision = None
    disc_number = None
    disc_total = None

    # Artifact-local naming evidence is usable only when it explicitly
    # belongs to the selected canonical platform. Contradictory or
    # unscoped local metadata must not alter the proposed filename.
    #
    # Catalogue release names can already contain region, language,
    # revision, and media qualifiers. Without a distinct structured
    # title, do not append fields that would require parsing the provider
    # string to avoid duplication.
    if structured_title and local_platform_agrees:
        region = _first_local_value(
            metadata,
            "countries",
        )

        if region is None:
            region = _first_local_value(
                metadata,
                "regions",
            )

        revision = _first_local_value(
            metadata,
            "release_revisions",
        )

        if revision is not None:
            revision = str(revision).strip()

            if revision.lower() in {
                "",
                "0",
                "rev 0",
                "revision 0",
            }:
                revision = None

        number = _first_local_value(
            metadata,
            "disc_numbers",
        )
        total = _first_local_value(
            metadata,
            "disc_totals",
        )

        if (
            isinstance(number, int)
            and not isinstance(number, bool)
            and isinstance(total, int)
            and not isinstance(total, bool)
            and total > 1
            and 1 <= number <= total
        ):
            disc_number = number
            disc_total = total

    return NamingInput(
        title=title,
        title_is_structured=structured_title,
        platform=platform,
        primary_identifier=identifier,
        region=(
            None
            if region is None
            else str(region)
        ),
        revision=revision,
        disc_number=disc_number,
        disc_total=disc_total,
    )


@dataclass(frozen=True, slots=True)
class RenamePlan:
    """A non-mutating proposal for canonical file naming."""

    source_name: str
    destination_name: str
    reason: str
    safe_to_apply: bool
    operation: str = "copy"
    conflicts: tuple[str, ...] = ()
    content_known_good: bool = False
    representation_known_good: bool = False

    def __post_init__(self) -> None:
        if self.operation not in {
            "copy",
            "replace",
            "rename",
        }:
            raise ValueError(
                "rename operation must be "
                "'copy', 'replace', or 'rename'"
            )


@dataclass(frozen=True, slots=True)
class NamingPolicy:
    """Generate filenames from canonical release identity."""

    preserve_extension: bool = True

    def canonical_filename(
        self,
        identity: CanonicalReleaseIdentity,
        *,
        extension: str | None = None,
    ) -> str:
        base = sanitize_filename_component(identity.release_name)

        if extension is None or not self.preserve_extension:
            return base

        normalized_extension = extension.strip().lstrip(".")

        if not normalized_extension:
            return base

        return f"{base}.{normalized_extension}"

    def structured_filename(
        self,
        naming: NamingInput,
        *,
        extension: str | None = None,
    ) -> str:
        """Generate a filename from explicitly selected naming evidence."""

        parts = [
            sanitize_filename_component(
                naming.title
            )
        ]

        if naming.primary_identifier is not None:
            identifier = sanitize_filename_component(
                naming.primary_identifier
            )
            parts.append(f"[{identifier}]")

        if naming.title_is_structured:
            if naming.region is not None:
                region = sanitize_filename_component(
                    naming.region
                )
                parts.append(f"({region})")

            if (
                naming.disc_number is not None
                and naming.disc_total is not None
                and naming.disc_total > 1
            ):
                parts.append(
                    "("
                    f"Disc {naming.disc_number} "
                    f"of {naming.disc_total}"
                    ")"
                )

            if naming.media_qualifier is not None:
                qualifier = sanitize_filename_component(
                    naming.media_qualifier
                )
                parts.append(f"({qualifier})")

            if naming.revision is not None:
                revision = sanitize_filename_component(
                    naming.revision
                )
                parts.append(f"(Rev {revision})")

        base = " ".join(parts)

        if extension is None or not self.preserve_extension:
            return base

        normalized_extension = extension.strip().lstrip(".")

        if not normalized_extension:
            return base

        return f"{base}.{normalized_extension}"

    def plan_identification_rename(
        self,
        source_name: str,
        result: IdentificationResult,
        *,
        verification: IdentificationVerification | None = None,
        operation: str = "copy",
    ) -> RenamePlan:
        """Plan a structured canonical filename from identification."""

        source = Path(source_name).name

        if not source:
            raise ValueError("source filename must not be empty")

        naming = naming_input_from_identification(result)
        extension = Path(source).suffix.lstrip(".") or None

        destination = self.structured_filename(
            naming,
            extension=extension,
        )

        canonical = result.canonical_match

        assert canonical is not None

        verification_conflicts = (
            ()
            if verification is None
            else tuple(
                conflict
                for report in (
                    verification.physical,
                    verification.normalized,
                )
                if report is not None
                for conflict in report.conflicts
            )
        )

        conflicts = tuple(
            dict.fromkeys(
                (
                    *canonical.conflicts,
                    *verification_conflicts,
                )
            )
        )

        content_known_good = bool(
            verification is not None
            and verification.content_known_good
        )
        representation_known_good = bool(
            verification is not None
            and verification.representation_known_good
        )

        return RenamePlan(
            source_name=source,
            destination_name=destination,
            reason="structured-identification",
            safe_to_apply=(
                verification is not None
                and verification.safe_for_canonical_naming
                and not conflicts
            ),
            operation=operation,
            conflicts=conflicts,
            content_known_good=content_known_good,
            representation_known_good=representation_known_good,
        )

    def plan_rename(
        self,
        source_name: str,
        identity: CanonicalReleaseIdentity,
        *,
        verification: IdentificationVerification | None = None,
        operation: str = "copy",
    ) -> RenamePlan:
        source = Path(source_name).name

        if not source:
            raise ValueError("source filename must not be empty")

        extension = Path(source).suffix.lstrip(".") or None

        destination = self.canonical_filename(
            identity,
            extension=extension,
        )

        verification_conflicts = (
            ()
            if verification is None
            else tuple(
                conflict
                for report in (
                    verification.physical,
                    verification.normalized,
                )
                if report is not None
                for conflict in report.conflicts
            )
        )

        conflicts = tuple(
            dict.fromkeys(
                (
                    *identity.conflicts,
                    *verification_conflicts,
                )
            )
        )

        content_known_good = bool(
            verification is not None
            and verification.content_known_good
        )
        representation_known_good = bool(
            verification is not None
            and verification.representation_known_good
        )

        return RenamePlan(
            source_name=source,
            destination_name=destination,
            reason="canonical-release-name",
            safe_to_apply=(
                verification is not None
                and verification.safe_for_canonical_naming
                and not conflicts
            ),
            operation=operation,
            conflicts=conflicts,
            content_known_good=content_known_good,
            representation_known_good=representation_known_good,
        )
