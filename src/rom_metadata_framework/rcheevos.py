from __future__ import annotations

import json
from pathlib import Path

from .backends import BackendSpec, run_backend
from .identity import AdapterProvenance, RomIdentity


RCHEEVOS_IDENTIFIER_NAMESPACE = "retroachievements"
RCHEEVOS_HELPER_EXECUTABLE = "rom-metadata-rcheevos"
RCHEEVOS_HELPER_SCHEMA_VERSION = 1


class RcheevosResponseError(RuntimeError):
    """Raised when the rcheevos helper returns an invalid success response."""


class RcheevosAdapter:
    """ROM identification adapter backed by the rcheevos helper."""

    name = "rcheevos"

    def __init__(
        self,
        *,
        console_id: int,
        platform: str | None = None,
        executable: str = RCHEEVOS_HELPER_EXECUTABLE,
    ) -> None:
        if console_id <= 0:
            raise ValueError("console_id must be greater than zero")

        self.console_id = console_id
        self.platform = platform.strip() if platform is not None else None

        if self.platform == "":
            self.platform = None

        self.backend = BackendSpec(
            name=self.name,
            executable=executable,
        )

    def supports(self, path: Path) -> bool:
        """Return whether the supplied path is a regular file."""

        return Path(path).is_file()

    def identify(self, path: Path) -> RomIdentity:
        """Generate a RetroAchievements identifier for one ROM."""

        path = Path(path)

        result = run_backend(
            self.backend,
            (
                "hash",
                "--console-id",
                str(self.console_id),
                "--json",
                str(path),
            ),
        )

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RcheevosResponseError(
                "rcheevos helper returned invalid JSON"
            ) from exc

        if not isinstance(payload, dict):
            raise RcheevosResponseError(
                "rcheevos helper response must be a JSON object"
            )

        if payload.get("schema_version") != RCHEEVOS_HELPER_SCHEMA_VERSION:
            raise RcheevosResponseError(
                "unsupported rcheevos helper schema version"
            )

        if payload.get("console_id") != self.console_id:
            raise RcheevosResponseError(
                "rcheevos helper returned an unexpected console ID"
            )

        if payload.get("backend") != "rcheevos":
            raise RcheevosResponseError(
                "rcheevos helper returned an unexpected backend"
            )

        identifier = payload.get("hash")
        backend_version = payload.get("backend_version")

        if not isinstance(identifier, str):
            raise RcheevosResponseError(
                "rcheevos helper response is missing a hash"
            )

        identifier = identifier.strip().lower()

        if len(identifier) != 32 or any(
            character not in "0123456789abcdef"
            for character in identifier
        ):
            raise RcheevosResponseError(
                "rcheevos helper returned an invalid hash"
            )

        if not isinstance(backend_version, str):
            raise RcheevosResponseError(
                "rcheevos helper response is missing backend_version"
            )

        backend_version = backend_version.strip()

        if not backend_version:
            raise RcheevosResponseError(
                "rcheevos helper returned an empty backend_version"
            )

        return RomIdentity(
            platform=self.platform,
            format=path.suffix.lower().lstrip(".") or None,
            specialized_identifiers={
                RCHEEVOS_IDENTIFIER_NAMESPACE: identifier,
            },
            adapter=AdapterProvenance(
                name=self.name,
                version=backend_version,
                backend="rom-metadata-rcheevos",
            ),
        )


def adapter_for_platform(
    platform: str,
    *,
    executable: str = RCHEEVOS_HELPER_EXECUTABLE,
) -> RcheevosAdapter:
    """Create a rcheevos adapter from a framework platform name or alias."""

    from .platforms import canonical_platform_name, rcheevos_console_id

    canonical = canonical_platform_name(platform)

    return RcheevosAdapter(
        console_id=rcheevos_console_id(canonical),
        platform=canonical,
        executable=executable,
    )
