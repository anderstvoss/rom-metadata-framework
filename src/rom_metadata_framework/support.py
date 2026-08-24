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
    integrity: PlatformCapabilityKind
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
    integrity: PlatformCapabilityKind = PlatformCapabilityKind.NONE
    normalization_backend: str | None = None
    notes: tuple[str, ...] = ()


_IMPLEMENTED_SUPPORT: dict[str, _RuntimePlatformSupport] = {
    "nes": _RuntimePlatformSupport(
        status=PlatformImplementationStatus.SUPPORTED,
        detection=PlatformCapabilityKind.BUILT_IN,
        inspection=PlatformCapabilityKind.NONE,
        integrity=PlatformCapabilityKind.NONE,
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
        integrity=PlatformCapabilityKind.NONE,
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
        integrity=PlatformCapabilityKind.NONE,
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
        integrity=PlatformCapabilityKind.NONE,
        normalization=PlatformCapabilityKind.NONE,
        notes=(
            "bounded ISO9660 SYSTEM.CNF/BOOT2 inspection",
        ),
    ),
    "ps3": _RuntimePlatformSupport(
        status=PlatformImplementationStatus.SUPPORTED,
        detection=PlatformCapabilityKind.BUILT_IN,
        inspection=PlatformCapabilityKind.BUILT_IN,
        integrity=PlatformCapabilityKind.NONE,
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
        integrity=PlatformCapabilityKind.NONE,
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
        integrity=PlatformCapabilityKind.NONE,
        normalization=PlatformCapabilityKind.NONE,
        notes=(
            "bounded XDVDFS/XEX2 structural inspection",
        ),
    ),
    "switch": _RuntimePlatformSupport(
        status=PlatformImplementationStatus.SUPPORTED,
        detection=PlatformCapabilityKind.BUILT_IN,
        inspection=PlatformCapabilityKind.BUILT_IN,
        integrity=PlatformCapabilityKind.NONE,
        normalization=PlatformCapabilityKind.NONE,
        notes=(
            "bounded NSP/PFS0 and XCI/HFS0 structural support",
            "NCA decryption is outside the current implementation",
        ),
    ),
}


class _DefaultComponentKind(StrEnum):
    """Private standard-runtime component categories."""

    DETECTOR = "detector"
    INSPECTOR = "inspector"
    NORMALIZER = "normalizer"
    INTEGRITY_VERIFIER = "integrity-verifier"


# One default component may implement more than one canonical platform.
#
# This table intentionally describes routing ownership rather than public
# support quality. Runtime construction remains explicit in defaults.py,
# while public support semantics remain in _IMPLEMENTED_SUPPORT.
#
# Keeping ownership in one table means a new component has one declarative
# registration point regardless of which capability category it implements.
_DEFAULT_COMPONENT_PLATFORMS: dict[
    _DefaultComponentKind,
    dict[str, tuple[str, ...]],
] = {
    _DefaultComponentKind.DETECTOR: {
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
    },
    _DefaultComponentKind.INSPECTOR: {
        "ps2": ("ps2",),
        "ps3": ("ps3",),
        "xbox360": ("xbox360",),
        "switch": ("switch",),
    },
    _DefaultComponentKind.NORMALIZER: {
        "nes": ("nes",),
        "dolphin": (
            "gc",
            "wii",
        ),
        "xbox": ("xbox",),
    },
    _DefaultComponentKind.INTEGRITY_VERIFIER: {},
}


def _default_component_platforms(
    kind: _DefaultComponentKind,
) -> dict[str, tuple[str, ...]]:
    """Return standard-runtime ownership for one component category."""

    return _DEFAULT_COMPONENT_PLATFORMS[kind]


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
                integrity=PlatformCapabilityKind.NONE,
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
                integrity=support.integrity,
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
        build_default_integrity_verifier,
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
    integrity_verifiers = tuple(
        verifier.name
        for verifier in build_default_integrity_verifier().verifiers
    )

    detector_ownership = _default_component_platforms(
        _DefaultComponentKind.DETECTOR
    )
    inspector_ownership = _default_component_platforms(
        _DefaultComponentKind.INSPECTOR
    )
    normalizer_ownership = _default_component_platforms(
        _DefaultComponentKind.NORMALIZER
    )
    integrity_ownership = _default_component_platforms(
        _DefaultComponentKind.INTEGRITY_VERIFIER
    )

    expected_detectors = tuple(
        detector_ownership
    )
    expected_inspectors = tuple(
        inspector_ownership
    )
    expected_normalizers = tuple(
        normalizer_ownership
    )
    expected_integrity_verifiers = tuple(
        integrity_ownership
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

    if integrity_verifiers != expected_integrity_verifiers:
        problems.append(
            "default integrity-verifier composition does not match "
            "support inventory ownership"
        )

    detection_platforms = _flatten_component_platforms(
        detector_ownership
    )
    inspection_platforms = _flatten_component_platforms(
        inspector_ownership
    )
    normalization_platforms = _flatten_component_platforms(
        normalizer_ownership
    )
    integrity_platforms = _flatten_component_platforms(
        integrity_ownership
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
        has_integrity = (
            support.integrity
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

        if has_integrity != (
            platform in integrity_platforms
        ):
            problems.append(
                f"{platform}: integrity support disagrees "
                "with default integrity-verifier routing"
            )

        operational = (
            has_detection
            or has_inspection
            or has_normalization
            or has_integrity
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
