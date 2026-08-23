from dataclasses import FrozenInstanceError

import pytest

from rom_metadata_framework.canonical import CanonicalReleaseIdentity
from rom_metadata_framework.metadata import (
    MetadataProvenance,
    MetadataValue,
    ReleaseMetadata,
)
from rom_metadata_framework.metadata_collection import (
    MetadataCollectionReport,
    MetadataProviderCollection,
)
from rom_metadata_framework.metadata_provider import (
    MetadataProviderResult,
)


def identity() -> CanonicalReleaseIdentity:
    return CanonicalReleaseIdentity(
        release_name="Example Game (USA)",
        platform="nes",
        source="catalogue",
        source_id="release-1",
    )



class Provider:
    def __init__(
        self,
        name: str,
        result: MetadataProviderResult | None,
        calls: list[str] | None = None,
    ) -> None:
        self._name = name
        self.result = result
        self.calls = calls

    @property
    def name(self) -> str:
        return self._name

    def lookup_metadata(self, identity):
        if self.calls is not None:
            self.calls.append(self._name)
        return self.result



def result(
    provider: str,
    provider_id: str,
) -> MetadataProviderResult:
    return MetadataProviderResult(
        provider=provider,
        provider_id=provider_id,
        metadata=ReleaseMetadata(),
    )



def test_empty_collection_returns_empty_report() -> None:
    report = MetadataProviderCollection(providers=()).collect(identity())

    assert report.attempted == ()
    assert report.matched == ()
    assert report.unmatched == ()
    assert report.results == ()


def test_collection_preserves_registration_order() -> None:
    collection = MetadataProviderCollection(
        providers=(
            Provider("first", result("first", "1")),
            Provider("second", result("second", "2")),
            Provider("third", result("third", "3")),
        ),
    )

    report = collection.collect(identity())

    assert report.attempted == ("first", "second", "third")
    assert report.matched == ("first", "second", "third")
    assert report.unmatched == ()


def test_collection_records_unmatched_providers() -> None:
    collection = MetadataProviderCollection(
        providers=(
            Provider("first", result("first", "1")),
            Provider("missing", None),
            Provider("third", result("third", "3")),
        ),
    )

    report = collection.collect(identity())

    assert report.attempted == ("first", "missing", "third")
    assert report.matched == ("first", "third")
    assert report.unmatched == ("missing",)
    assert tuple(item.provider for item in report.results) == (
        "first",
        "third",
    )


def test_collection_calls_every_provider_in_order() -> None:
    calls = []

    collection = MetadataProviderCollection(
        providers=(
            Provider("first", None, calls),
            Provider("second", result("second", "2"), calls),
            Provider("third", None, calls),
        ),
    )

    collection.collect(identity())

    assert calls == ["first", "second", "third"]


def test_collection_preserves_matched_empty_metadata() -> None:
    collection = MetadataProviderCollection(
        providers=(
            Provider(
                "provider-a",
                result("provider-a", "record-1"),
            ),
        ),
    )

    report = collection.collect(identity())

    assert report.matched == ("provider-a",)
    assert len(report.results) == 1
    assert report.results[0].metadata == ReleaseMetadata()


def test_collection_preserves_independent_provider_evidence() -> None:
    a = MetadataProvenance(
        source="provider-a",
        source_id="a-field",
    )
    b = MetadataProvenance(
        source="provider-b",
        source_id="b-field",
    )

    collection = MetadataProviderCollection(
        providers=(
            Provider(
                "provider-a",
                MetadataProviderResult(
                    provider="provider-a",
                    provider_id="a-record",
                    metadata=ReleaseMetadata(
                        developers=(
                            MetadataValue(
                                value="Studio A",
                                provenance=a,
                            ),
                        ),
                    ),
                ),
            ),
            Provider(
                "provider-b",
                MetadataProviderResult(
                    provider="provider-b",
                    provider_id="b-record",
                    metadata=ReleaseMetadata(
                        developers=(
                            MetadataValue(
                                value="Studio B",
                                provenance=b,
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )

    report = collection.collect(identity())

    assert len(report.results) == 2
    assert (
        report.results[0].metadata.developers[0].value
        == "Studio A"
    )
    assert (
        report.results[1].metadata.developers[0].value
        == "Studio B"
    )


def test_collection_rejects_empty_provider_name() -> None:
    with pytest.raises(ValueError):
        MetadataProviderCollection(
            providers=(Provider("  ", None),),
        )


def test_collection_rejects_duplicate_provider_names() -> None:
    with pytest.raises(ValueError):
        MetadataProviderCollection(
            providers=(
                Provider("Provider-A", None),
                Provider(" provider-a ", None),
            ),
        )


def test_collection_rejects_misattributed_result() -> None:
    collection = MetadataProviderCollection(
        providers=(
            Provider(
                "provider-a",
                result("provider-b", "record-1"),
            ),
        ),
    )

    with pytest.raises(
        ValueError,
        match="result source does not match",
    ):
        collection.collect(identity())


def test_provider_exception_propagates() -> None:
    class FailingProvider:
        name = "failing"

        def lookup_metadata(self, identity):
            raise RuntimeError("provider failed")

    collection = MetadataProviderCollection(
        providers=(FailingProvider(),),
    )

    with pytest.raises(RuntimeError, match="provider failed"):
        collection.collect(identity())


def test_collection_report_is_frozen() -> None:
    report = MetadataCollectionReport(
        attempted=("provider-a",),
        unmatched=("provider-a",),
        results=(),
    )

    with pytest.raises(FrozenInstanceError):
        report.attempted = ()


def test_collection_report_normalizes_provider_names() -> None:
    report = MetadataCollectionReport(
        attempted=(" Provider-A ", " PROVIDER-B "),
        unmatched=(" provider-b ",),
        results=(result("provider-a", "1"),),
    )

    assert report.attempted == ("provider-a", "provider-b")
    assert report.matched == ("provider-a",)
    assert report.unmatched == ("provider-b",)


def test_collection_report_rejects_unattempted_unmatched_provider() -> None:
    with pytest.raises(
        ValueError,
        match="must have been attempted",
    ):
        MetadataCollectionReport(
            attempted=("provider-a",),
            unmatched=("provider-b",),
            results=(result("provider-a", "1"),),
        )


def test_collection_report_rejects_unattempted_matched_provider() -> None:
    with pytest.raises(
        ValueError,
        match="must have been attempted",
    ):
        MetadataCollectionReport(
            attempted=("provider-a",),
            unmatched=(),
            results=(result("provider-b", "1"),),
        )


def test_collection_report_requires_complete_partition() -> None:
    with pytest.raises(
        ValueError,
        match="must partition attempted providers",
    ):
        MetadataCollectionReport(
            attempted=("provider-a", "provider-b"),
            unmatched=(),
            results=(result("provider-a", "1"),),
        )
