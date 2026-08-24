import pytest

from rom_metadata_framework.platforms import (
    PLATFORMS,
)
from rom_metadata_framework.support import (
    PlatformCapabilityKind,
    PlatformImplementationStatus,
    default_support_drift,
    platform_support,
    platform_support_inventory,
)


def test_inventory_covers_every_registered_platform() -> None:
    inventory = platform_support_inventory()

    assert tuple(
        item.platform
        for item in inventory
    ) == tuple(
        item.name
        for item in PLATFORMS
    )


def test_current_supported_platforms_are_explicit() -> None:
    supported = {
        item.platform
        for item in platform_support_inventory()
        if (
            item.status
            is PlatformImplementationStatus.SUPPORTED
        )
    }

    assert supported == {
        "nes",
        "gc",
        "wii",
        "ps2",
        "ps3",
        "xbox",
        "xbox360",
        "switch",
    }


def test_registry_only_platforms_have_no_runtime_support() -> None:
    for item in platform_support_inventory():
        if (
            item.status
            is not PlatformImplementationStatus.REGISTERED
        ):
            continue

        assert (
            item.detection
            is PlatformCapabilityKind.NONE
        )
        assert (
            item.inspection
            is PlatformCapabilityKind.NONE
        )
        assert (
            item.normalization
            is PlatformCapabilityKind.NONE
        )


def test_external_normalizers_report_backend() -> None:
    assert (
        platform_support(
            "gc"
        ).normalization_backend
        == "dolphin-tool"
    )

    assert (
        platform_support(
            "wii"
        ).normalization_backend
        == "dolphin-tool"
    )

    assert (
        platform_support(
            "xbox"
        ).normalization_backend
        == "xdvdfs"
    )


def test_rcheevos_mapping_is_derived_from_registry() -> None:
    assert platform_support(
        "ps2"
    ).rcheevos_mapping

    assert not platform_support(
        "ps3"
    ).rcheevos_mapping

    assert not platform_support(
        "xbox360"
    ).rcheevos_mapping

    assert not platform_support(
        "switch"
    ).rcheevos_mapping


def test_registered_platform_can_have_rcheevos_mapping() -> None:
    support = platform_support("snes")

    assert (
        support.status
        is PlatformImplementationStatus.REGISTERED
    )
    assert support.rcheevos_mapping


def test_unknown_support_lookup_raises_key_error() -> None:
    with pytest.raises(
        KeyError,
        match="not-a-platform",
    ):
        platform_support(
            "not-a-platform"
        )


def test_default_support_inventory_has_no_drift() -> None:
    assert default_support_drift() == ()


def test_support_inventory_exposes_platform_presentation_metadata() -> None:
    support = platform_support("ps3")

    assert support.platform == "ps3"
    assert support.display_name == "PlayStation 3"
    assert support.manufacturer == "Sony"


def test_integrity_support_is_initially_unimplemented() -> None:
    for item in platform_support_inventory():
        assert (
            item.integrity
            is PlatformCapabilityKind.NONE
        )


def test_default_component_ownership_covers_current_runtime() -> None:
    from rom_metadata_framework.defaults import (
        build_default_detector,
        build_default_inspector,
        build_default_integrity_verifier,
        build_default_normalizer,
    )
    from rom_metadata_framework.support import (
        _default_component_platforms,
        _DefaultComponentKind,
    )

    actual = {
        _DefaultComponentKind.DETECTOR: tuple(
            component.name
            for component in build_default_detector().detectors
        ),
        _DefaultComponentKind.INSPECTOR: tuple(
            component.name
            for component in build_default_inspector().inspectors
        ),
        _DefaultComponentKind.NORMALIZER: tuple(
            component.name
            for component in build_default_normalizer().normalizers
        ),
        _DefaultComponentKind.INTEGRITY_VERIFIER: tuple(
            component.name
            for component in (
                build_default_integrity_verifier().verifiers
            )
        ),
    }

    for kind, names in actual.items():
        assert names == tuple(
            _default_component_platforms(kind)
        )


def test_default_component_ownership_references_registered_platforms() -> None:
    from rom_metadata_framework.support import (
        _DEFAULT_COMPONENT_PLATFORMS,
    )

    registered = {
        platform.name
        for platform in PLATFORMS
    }

    for ownership in _DEFAULT_COMPONENT_PLATFORMS.values():
        for platforms in ownership.values():
            assert platforms
            assert set(platforms) <= registered
            assert len(platforms) == len(set(platforms))
