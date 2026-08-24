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
