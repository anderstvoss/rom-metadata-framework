from __future__ import annotations

from dataclasses import dataclass

from .platforms import canonical_platform_name


@dataclass(frozen=True, slots=True)
class RequestedIdentity:
    """User-supplied platform-native identity hypothesis."""

    platform: str
    identifier: str

    def __post_init__(self) -> None:
        platform = canonical_platform_name(self.platform)
        identifier = self.identifier.strip()

        if not identifier:
            raise ValueError(
                "requested identity identifier must not be empty"
            )

        object.__setattr__(
            self,
            "platform",
            platform,
        )
        object.__setattr__(
            self,
            "identifier",
            identifier,
        )

    @classmethod
    def parse(
        cls,
        value: str,
    ) -> RequestedIdentity:
        """Parse PLATFORM:IDENTIFIER syntax."""

        raw = value.strip()

        if ":" not in raw:
            raise ValueError(
                "identity must use PLATFORM:IDENTIFIER syntax"
            )

        platform, identifier = raw.split(":", 1)

        if not platform.strip():
            raise ValueError(
                "identity platform must not be empty"
            )

        return cls(
            platform=platform,
            identifier=identifier,
        )


@dataclass(frozen=True, slots=True)
class IdentificationSelection:
    """Optional platform or identity direction for identification.

    Without ``restrict``, the platform acts as a preferred hint and the
    caller may fall back to unrestricted handling.

    With ``restrict``, unrelated platform work must not be invoked.
    """

    platform: str | None = None
    identity: RequestedIdentity | None = None
    restrict: bool = False

    def __post_init__(self) -> None:
        platform = (
            canonical_platform_name(self.platform)
            if self.platform is not None
            else None
        )

        identity = self.identity

        if identity is not None:
            if platform is None:
                platform = identity.platform
            elif platform != identity.platform:
                raise ValueError(
                    "requested platform and identity platform disagree"
                )

        if self.restrict and platform is None:
            raise ValueError(
                "restrict requires a platform or identity"
            )

        object.__setattr__(
            self,
            "platform",
            platform,
        )

    @property
    def effective_platform(self) -> str | None:
        """Return the platform implied by the selection."""

        return self.platform


_SHARED_COMPONENT_PLATFORMS = {
    "dolphin": frozenset(
        {
            "gc",
            "wii",
        }
    ),
}


def component_supports_platform(
    component_name: str,
    platform: str,
) -> bool:
    """Return whether one runtime component owns a platform."""

    name = component_name.strip().lower()

    if not name:
        raise ValueError(
            "component name must not be empty"
        )

    canonical = canonical_platform_name(
        platform
    )

    shared = _SHARED_COMPONENT_PLATFORMS.get(
        name
    )

    if shared is not None:
        return canonical in shared

    return name == canonical


_PRIMARY_IDENTITY_NAMESPACES = {
    "gc": "nintendo-game-id",
    "wii": "nintendo-game-id",
    "ps2": "ps2-product-code",
    "ps3": "ps3-title-id",
    "xbox": "xbox-title-id",
    "xbox360": "xbox360-title-id",
    "switch": "switch-application-id",
}


def primary_identity_namespace(
    platform: str,
) -> str | None:
    """Return the native identifier namespace used by PLATFORM."""

    canonical = canonical_platform_name(platform)

    return _PRIMARY_IDENTITY_NAMESPACES.get(
        canonical
    )


def local_primary_identifier(
    metadata,
    *,
    platform: str,
) -> str | None:
    """Extract the primary native ID from agreeing local metadata."""

    if metadata is None:
        return None

    canonical = canonical_platform_name(platform)

    if metadata.platform != canonical:
        return None

    namespace = primary_identity_namespace(
        canonical
    )

    if namespace is None:
        return None

    for identifier in metadata.identifiers:
        if identifier.namespace == namespace:
            return identifier.value

    return None


def identifiers_equal(
    observed: str,
    requested: str,
) -> bool:
    """Compare native platform identifiers conservatively."""

    return (
        observed.strip().casefold()
        == requested.strip().casefold()
    )
