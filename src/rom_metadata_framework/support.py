from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .platforms import (
    BACKEND_PLATFORM_MAPPINGS,
    PLATFORMS,
)


class PlatformImplementationStatus(StrEnum):
    """Public implementation state of one registered platform."""

    SUPPORTED = "supported"
    REGISTERED = "registered"


class PlatformCapabilityKind(StrEnum):
    """How one platform capability is implemented."""

    BUILT_IN = "built-in"
    EXTERNAL = "external"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class PlatformSupport:
    """Public support summary for one canonical platform."""

    platform: str
    display_name: str
    manufacturer: str
    status: PlatformImplementationStatus
    detection: PlatformCapabilityKind
    inspection: PlatformCapabilityKind
    normalization: PlatformCapabilityKind
    normalization_backend: str | None = None
    rcheevos_mapping: bool = False
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _RuntimePlatformSupport:
    """Private runtime-capability declaration for one platform."""

    status: PlatformImplementationStatus
    detection: PlatformCapabilityKind
    inspection: PlatformCapabilityKind
    normalization: PlatformCapabilityKind
    normalization_backend: str | None = None
    notes: tuple[str, ...] = ()


_IMPLEMENTED_SUPPORT: dict[str, _RuntimePlatformSupport] = {
    "nes": _RuntimePlatformSupport(
        status=PlatformImplementationStatus.SUPPORTED,
        detection=PlatformCapabilityKind.BUILT_IN,
        inspection=PlatformCapabilityKind.NONE,
        normalization=PlatformCapabilityKind.BUILT_IN,
        notes=(
            "iNES/NES content support",
            "headerless normalization is explicit opt-in",
        ),
    ),
    "gc": _RuntimePlatformSupport(
        status=PlatformImplementationStatus.SUPPORTED,
        detection=PlatformCapabilityKind.EXTERNAL,
        inspection=PlatformCapabilityKind.NONE,
        normalization=PlatformCapabilityKind.EXTERNAL,
        normalization_backend="dolphin-tool",
        notes=(
            "detection and normalization use the Dolphin backend",
        ),
    ),
    "wii": _RuntimePlatformSupport(
        status=PlatformImplementationStatus.SUPPORTED,
        detection=PlatformCapabilityKind.EXTERNAL,
        inspection=PlatformCapabilityKind.NONE,
        normalization=PlatformCapabilityKind.EXTERNAL,
        normalization_backend="dolphin-tool",
        notes=(
            "detection and normalization use the Dolphin backend",
        ),
    ),
    "ps2": _RuntimePlatformSupport(
        status=PlatformImplementationStatus.SUPPORTED,
        detection=PlatformCapabilityKind.BUILT_IN,
        inspection=PlatformCapabilityKind.BUILT_IN,
        normalization=PlatformCapabilityKind.NONE,
        notes=(
            "bounded ISO9660 SYSTEM.CNF/BOOT2 inspection",
        ),
    ),
    "ps3": _RuntimePlatformSupport(
        status=PlatformImplementationStatus.SUPPORTED,
        detection=PlatformCapabilityKind.BUILT_IN,
        inspection=PlatformCapabilityKind.BUILT_IN,
        normalization=PlatformCapabilityKind.NONE,
        notes=(
            "directly readable ISO9660 disc images only",
            "encrypted/raw representations are not decoded",
        ),
    ),
    "xbox": _RuntimePlatformSupport(
        status=PlatformImplementationStatus.SUPPORTED,
        detection=PlatformCapabilityKind.EXTERNAL,
        inspection=PlatformCapabilityKind.NONE,
        normalization=PlatformCapabilityKind.EXTERNAL,
        normalization_backend="xdvdfs",
        notes=(
            "XDVDFS support uses the external xdvdfs backend",
        ),
    ),
    "xbox360": _RuntimePlatformSupport(
        status=PlatformImplementationStatus.SUPPORTED,
        detection=PlatformCapabilityKind.BUILT_IN,
        inspection=PlatformCapabilityKind.BUILT_IN,
        normalization=PlatformCapabilityKind.NONE,
        notes=(
            "bounded XDVDFS/XEX2 structural inspection",
        ),
    ),
    "switch": _RuntimePlatformSupport(
        status=PlatformImplementationStatus.SUPPORTED,
        detection=PlatformCapabilityKind.BUILT_IN,
        inspection=PlatformCapabilityKind.BUILT_IN,
        normalization=PlatformCapabilityKind.NONE,
        notes=(
            "bounded NSP/PFS0 and XCI/HFS0 structural support",
            "NCA decryption is outside the current implementation",
        ),
    ),
}


# One default component may implement more than one canonical platform.
#
# These maps intentionally describe routing ownership rather than public
# support quality. Public support semantics remain in _IMPLEMENTED_SUPPORT.
_DEFAULT_DETECTOR_PLATFORMS: dict[str, tuple[str, ...]] = {
    "nes": ("nes",),
    "ps2": ("ps2",),
    "ps3": ("ps3",),
    "dolphin": (
        "gc",
        "wii",
    ),
    "xbox360": ("xbox360",),
    "switch": ("switch",),
    "xbox": ("xbox",),
}

_DEFAULT_INSPECTOR_PLATFORMS: dict[str, tuple[str, ...]] = {
    "ps2": ("ps2",),
    "ps3": ("ps3",),
    "xbox360": ("xbox360",),
    "switch": ("switch",),
}

_DEFAULT_NORMALIZER_PLATFORMS: dict[str, tuple[str, ...]] = {
    "nes": ("nes",),
    "dolphin": (
        "gc",
        "wii",
    ),
    "xbox": ("xbox",),
}


def _rcheevos_platforms() -> frozenset[str]:
    return frozenset(
        mapping.platform
        for mapping in BACKEND_PLATFORM_MAPPINGS
        if mapping.backend == "rcheevos"
    )


def platform_support_inventory() -> tuple[PlatformSupport, ...]:
    """Return support state for every registered canonical platform."""

    rcheevos = _rcheevos_platforms()
    result = []

    for definition in PLATFORMS:
        support = _IMPLEMENTED_SUPPORT.get(
            definition.name
        )

        if support is None:
            support = _RuntimePlatformSupport(
                status=(
                    PlatformImplementationStatus.REGISTERED
                ),
                detection=PlatformCapabilityKind.NONE,
                inspection=PlatformCapabilityKind.NONE,
                normalization=PlatformCapabilityKind.NONE,
            )

        result.append(
            PlatformSupport(
                platform=definition.name,
                display_name=definition.display_name,
                manufacturer=definition.manufacturer,
                status=support.status,
                detection=support.detection,
                inspection=support.inspection,
                normalization=support.normalization,
                normalization_backend=(
                    support.normalization_backend
                ),
                rcheevos_mapping=(
                    definition.name in rcheevos
                ),
                notes=support.notes,
            )
        )

    return tuple(result)


def platform_support(
    platform: str,
) -> PlatformSupport:
    """Return the support record for one canonical platform."""

    for item in platform_support_inventory():
        if item.platform == platform:
            return item

    raise KeyError(platform)


def _flatten_component_platforms(
    mapping: dict[str, tuple[str, ...]],
) -> frozenset[str]:
    return frozenset(
        platform
        for platforms in mapping.values()
        for platform in platforms
    )


def default_support_drift() -> tuple[str, ...]:
    """Report inconsistencies between support data and default routing.

    This is primarily a development-time invariant. Keeping it in the
    package also makes the support model directly testable without parsing
    documentation or relying on implementation-module naming conventions.
    """

    # Imported lazily so the public support model does not participate in
    # construction of the default runtime.
    from .defaults import (
        build_default_detector,
        build_default_inspector,
        build_default_normalizer,
    )

    problems: list[str] = []

    detectors = tuple(
        detector.name
        for detector in build_default_detector().detectors
    )
    inspectors = tuple(
        inspector.name
        for inspector in build_default_inspector().inspectors
    )
    normalizers = tuple(
        normalizer.name
        for normalizer in build_default_normalizer().normalizers
    )

    expected_detectors = tuple(
        _DEFAULT_DETECTOR_PLATFORMS
    )
    expected_inspectors = tuple(
        _DEFAULT_INSPECTOR_PLATFORMS
    )
    expected_normalizers = tuple(
        _DEFAULT_NORMALIZER_PLATFORMS
    )

    if detectors != expected_detectors:
        problems.append(
            "default detector composition does not match "
            "support inventory ownership"
        )

    if inspectors != expected_inspectors:
        problems.append(
            "default inspector composition does not match "
            "support inventory ownership"
        )

    if normalizers != expected_normalizers:
        problems.append(
            "default normalizer composition does not match "
            "support inventory ownership"
        )

    detection_platforms = _flatten_component_platforms(
        _DEFAULT_DETECTOR_PLATFORMS
    )
    inspection_platforms = _flatten_component_platforms(
        _DEFAULT_INSPECTOR_PLATFORMS
    )
    normalization_platforms = _flatten_component_platforms(
        _DEFAULT_NORMALIZER_PLATFORMS
    )

    inventory = {
        item.platform: item
        for item in platform_support_inventory()
    }

    registered = {
        definition.name
        for definition in PLATFORMS
    }

    described = set(inventory)

    if described != registered:
        problems.append(
            "support inventory does not cover exactly the "
            "registered canonical platforms"
        )

    for platform, support in inventory.items():
        has_detection = (
            support.detection
            is not PlatformCapabilityKind.NONE
        )
        has_inspection = (
            support.inspection
            is not PlatformCapabilityKind.NONE
        )
        has_normalization = (
            support.normalization
            is not PlatformCapabilityKind.NONE
        )

        if has_detection != (
            platform in detection_platforms
        ):
            problems.append(
                f"{platform}: detection support disagrees "
                "with default detector routing"
            )

        if has_inspection != (
            platform in inspection_platforms
        ):
            problems.append(
                f"{platform}: inspection support disagrees "
                "with default inspector routing"
            )

        if has_normalization != (
            platform in normalization_platforms
        ):
            problems.append(
                f"{platform}: normalization support disagrees "
                "with default normalizer routing"
            )

        operational = (
            has_detection
            or has_inspection
            or has_normalization
        )

        if operational != (
            support.status
            is PlatformImplementationStatus.SUPPORTED
        ):
            problems.append(
                f"{platform}: implementation status disagrees "
                "with default runtime support"
            )

        if (
            support.normalization
            is PlatformCapabilityKind.EXTERNAL
            and support.normalization_backend is None
        ):
            problems.append(
                f"{platform}: external normalization is "
                "missing its backend name"
            )

        if (
            support.normalization
            is not PlatformCapabilityKind.EXTERNAL
            and support.normalization_backend is not None
        ):
            problems.append(
                f"{platform}: normalization backend is set "
                "without external normalization"
            )

    return tuple(problems)
