from pathlib import Path

import pytest

from rom_metadata_framework.contracts import (
    InspectionContractError,
)
from rom_metadata_framework.inspection import (
    AmbiguousStructuralInspectorError,
    CompositeStructuralInspector,
    StructuralInspectionResult,
)
from rom_metadata_framework.local_metadata import (
    LocalContentMetadata,
)
from rom_metadata_framework.representation import (
    RepresentationIdentity,
)


class FakeInspector:
    def __init__(
        self,
        name: str,
        result: StructuralInspectionResult | None,
    ) -> None:
        self.name = name
        self.result = result

    def inspect(
        self,
        path: Path,
    ) -> StructuralInspectionResult | None:
        return self.result


def result() -> StructuralInspectionResult:
    return StructuralInspectionResult(
        physical_representation=RepresentationIdentity(
            kind="disc-image",
            format="iso9660",
        ),
        local_metadata=LocalContentMetadata(
            platform="ps2",
        ),
    )


def test_structural_result_requires_evidence() -> None:
    with pytest.raises(
        ValueError,
        match="at least one",
    ):
        StructuralInspectionResult()


def test_composite_returns_only_matching_inspector(
    tmp_path: Path,
) -> None:
    router = CompositeStructuralInspector(
        (
            FakeInspector("first", None),
            FakeInspector("second", result()),
        )
    )

    inspected = router.inspect(
        tmp_path / "game.iso"
    )

    assert inspected == result()


def test_composite_returns_none_when_unsupported(
    tmp_path: Path,
) -> None:
    router = CompositeStructuralInspector(
        (
            FakeInspector("first", None),
        )
    )

    assert router.inspect(tmp_path / "game.bin") is None


def test_composite_rejects_ambiguous_matches(
    tmp_path: Path,
) -> None:
    router = CompositeStructuralInspector(
        (
            FakeInspector("first", result()),
            FakeInspector("second", result()),
        )
    )

    with pytest.raises(
        AmbiguousStructuralInspectorError,
        match="first, second",
    ):
        router.inspect(tmp_path / "game.iso")


def test_composite_rejects_invalid_result(
    tmp_path: Path,
) -> None:
    class InvalidInspector:
        name = "invalid"

        def inspect(self, path: Path):
            return "invalid"

    router = CompositeStructuralInspector(
        (
            InvalidInspector(),
        )
    )

    with pytest.raises(
        InspectionContractError,
        match="StructuralInspectionResult",
    ):
        router.inspect(tmp_path / "game.iso")


def test_composite_rejects_duplicate_names() -> None:
    with pytest.raises(
        ValueError,
        match="names must be unique",
    ):
        CompositeStructuralInspector(
            (
                FakeInspector("duplicate", None),
                FakeInspector("duplicate", None),
            )
        )


def test_structural_inspector_restricts_to_requested_platform(
    tmp_path,
) -> None:
    from rom_metadata_framework.inspection import (
        CompositeStructuralInspector,
        StructuralInspectionResult,
    )
    from rom_metadata_framework.local_metadata import (
        LocalContentMetadata,
    )

    calls = []

    class Inspector:
        def __init__(
            self,
            name,
            *,
            matches,
        ):
            self.name = name
            self.matches = matches

        def inspect(self, path):
            calls.append(self.name)

            if not self.matches:
                return None

            return StructuralInspectionResult(
                local_metadata=LocalContentMetadata(
                    platform=(
                        "wii"
                        if self.name == "dolphin"
                        else self.name
                    )
                )
            )

    path = tmp_path / "game.bin"
    path.write_bytes(b"x")

    inspector = CompositeStructuralInspector(
        (
            Inspector(
                "ps3",
                matches=True,
            ),
            Inspector(
                "dolphin",
                matches=True,
            ),
            Inspector(
                "xbox360",
                matches=True,
            ),
        )
    )

    result = inspector.inspect(
        path,
        preferred_platform="wii",
        restrict_platform=True,
    )

    assert calls == ["dolphin"]
    assert result is not None
    assert result.local_metadata is not None
    assert result.local_metadata.platform == "wii"


def test_structural_inspector_soft_hint_short_circuits(
    tmp_path,
) -> None:
    from rom_metadata_framework.inspection import (
        CompositeStructuralInspector,
        StructuralInspectionResult,
    )
    from rom_metadata_framework.local_metadata import (
        LocalContentMetadata,
    )

    calls = []

    class Inspector:
        def __init__(
            self,
            name,
            *,
            matches,
        ):
            self.name = name
            self.matches = matches

        def inspect(self, path):
            calls.append(self.name)

            if not self.matches:
                return None

            return StructuralInspectionResult(
                local_metadata=LocalContentMetadata(
                    platform="wii"
                )
            )

    path = tmp_path / "game.bin"
    path.write_bytes(b"x")

    inspector = CompositeStructuralInspector(
        (
            Inspector(
                "ps3",
                matches=True,
            ),
            Inspector(
                "dolphin",
                matches=True,
            ),
        )
    )

    result = inspector.inspect(
        path,
        preferred_platform="wii",
    )

    assert calls == ["dolphin"]
    assert result is not None


def test_structural_inspector_soft_hint_falls_back(
    tmp_path,
) -> None:
    from rom_metadata_framework.inspection import (
        CompositeStructuralInspector,
        StructuralInspectionResult,
    )
    from rom_metadata_framework.local_metadata import (
        LocalContentMetadata,
    )

    calls = []

    class Inspector:
        def __init__(
            self,
            name,
            *,
            matches,
        ):
            self.name = name
            self.matches = matches

        def inspect(self, path):
            calls.append(self.name)

            if not self.matches:
                return None

            return StructuralInspectionResult(
                local_metadata=LocalContentMetadata(
                    platform="ps3"
                )
            )

    path = tmp_path / "game.bin"
    path.write_bytes(b"x")

    inspector = CompositeStructuralInspector(
        (
            Inspector(
                "ps3",
                matches=True,
            ),
            Inspector(
                "dolphin",
                matches=False,
            ),
        )
    )

    result = inspector.inspect(
        path,
        preferred_platform="wii",
    )

    assert calls == [
        "dolphin",
        "ps3",
    ]
    assert result is not None
    assert result.local_metadata is not None
    assert result.local_metadata.platform == "ps3"


def test_configured_inspector_restricts_without_call_kwargs(
    tmp_path,
) -> None:
    from rom_metadata_framework.inspection import (
        CompositeStructuralInspector,
        StructuralInspectionResult,
    )
    from rom_metadata_framework.local_metadata import (
        LocalContentMetadata,
    )

    calls = []

    class Inspector:
        def __init__(self, name, matches):
            self.name = name
            self.matches = matches

        def inspect(self, path):
            calls.append(self.name)

            if not self.matches:
                return None

            return StructuralInspectionResult(
                local_metadata=LocalContentMetadata(
                    platform=(
                        "wii"
                        if self.name == "dolphin"
                        else self.name
                    )
                )
            )

    path = tmp_path / "game.bin"
    path.write_bytes(b"x")

    inspector = CompositeStructuralInspector(
        (
            Inspector("ps3", True),
            Inspector("dolphin", True),
        ),
        preferred_platform="wii",
        restrict_platform=True,
    )

    result = inspector.inspect(path)

    assert calls == ["dolphin"]
    assert result is not None
