from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .canonical import CanonicalReleaseIdentity


_INVALID_FILENAME_CHARACTERS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename_component(value: str) -> str:
    """Return a conservative cross-platform filename component."""

    value = _INVALID_FILENAME_CHARACTERS.sub("_", value)
    value = re.sub(r"\s+", " ", value)
    value = value.strip().rstrip(".")

    if not value:
        raise ValueError("canonical filename component is empty")

    return value


@dataclass(frozen=True, slots=True)
class RenamePlan:
    """A non-mutating proposal for canonical file naming."""

    source_name: str
    destination_name: str
    reason: str
    safe_to_apply: bool
    operation: str = "copy"
    conflicts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.operation not in {"copy", "replace"}:
            raise ValueError(
                "rename operation must be 'copy' or 'replace'"
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

    def plan_rename(
        self,
        source_name: str,
        identity: CanonicalReleaseIdentity,
        *,
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

        conflicts = identity.conflicts

        return RenamePlan(
            source_name=source,
            destination_name=destination,
            reason="canonical-release-name",
            safe_to_apply=(
                identity.has_authoritative_content_match
                and not conflicts
            ),
            operation=operation,
            conflicts=conflicts,
        )
