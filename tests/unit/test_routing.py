from dataclasses import dataclass
from pathlib import Path

import pytest

from rom_metadata_framework.content import (
    NormalizedContentIdentity,
)
from rom_metadata_framework.routing import (
    AmbiguousNormalizerError,
    CompositeNormalizer,
    NoSupportingNormalizerError,
)


@dataclass(frozen=True)
class FakeResult:
    content: NormalizedContentIdentity


class FakeNormalizer:
    def __init__(
        self,
        name: str,
        *,
        supports: bool,
    ) -> None:
        self.name = name
        self._supports = supports
        self.identify_calls = 0

    def supports(self, path: Path) -> bool:
        return self._supports

    def identify(self, path: Path) -> FakeResult:
        self.identify_calls += 1

        return FakeResult(
            content=NormalizedContentIdentity(
                kind=self.name,
            ),
        )


def test_composite_rejects_duplicate_names() -> None:
    with pytest.raises(ValueError):
        CompositeNormalizer(
            (
                FakeNormalizer(
                    "duplicate",
                    supports=False,
                ),
                FakeNormalizer(
                    "duplicate",
                    supports=False,
                ),
            )
        )


def test_composite_zero_matches_is_explicit(
    tmp_path: Path,
) -> None:
    path = tmp_path / "unknown.bin"
    path.write_bytes(b"unknown")

    first = FakeNormalizer(
        "first",
        supports=False,
    )
    second = FakeNormalizer(
        "second",
        supports=False,
    )

    router = CompositeNormalizer(
        (first, second)
    )

    assert router.supporting_normalizers(path) == ()

    with pytest.raises(NoSupportingNormalizerError):
        router.select(path)

    with pytest.raises(NoSupportingNormalizerError):
        router.identify(path)

    assert first.identify_calls == 0
    assert second.identify_calls == 0


def test_composite_routes_exactly_one_match(
    tmp_path: Path,
) -> None:
    path = tmp_path / "game.bin"
    path.write_bytes(b"game")

    first = FakeNormalizer(
        "first",
        supports=False,
    )
    second = FakeNormalizer(
        "second",
        supports=True,
    )

    router = CompositeNormalizer(
        (first, second)
    )

    assert router.supporting_normalizers(path) == (
        second,
    )
    assert router.select(path) is second

    result = router.identify(path)

    assert result.content.kind == "second"
    assert first.identify_calls == 0
    assert second.identify_calls == 1


def test_composite_rejects_ambiguous_match(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ambiguous.bin"
    path.write_bytes(b"ambiguous")

    first = FakeNormalizer(
        "first",
        supports=True,
    )
    second = FakeNormalizer(
        "second",
        supports=True,
    )

    router = CompositeNormalizer(
        (first, second)
    )

    assert router.supporting_normalizers(path) == (
        first,
        second,
    )

    with pytest.raises(
        AmbiguousNormalizerError,
    ) as exc_info:
        router.identify(path)

    assert exc_info.value.adapter_names == (
        "first",
        "second",
    )
    assert first.identify_calls == 0
    assert second.identify_calls == 0


def test_composite_selection_is_not_order_fallback(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ambiguous.bin"
    path.write_bytes(b"ambiguous")

    first = FakeNormalizer(
        "first",
        supports=True,
    )
    second = FakeNormalizer(
        "second",
        supports=True,
    )

    router = CompositeNormalizer(
        (second, first)
    )

    with pytest.raises(AmbiguousNormalizerError):
        router.identify(path)

    assert first.identify_calls == 0
    assert second.identify_calls == 0
