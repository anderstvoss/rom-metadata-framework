from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from .local_metadata import LocalContentMetadata
from .metadata_provider import MetadataProviderResult

COMPARABLE_METADATA_FIELDS = (
    "titles",
    "developers",
    "publishers",
    "regions",
    "languages",
    "player_counts",
    "multiplayer_features",
)


class MetadataFieldReconciliationStatus(StrEnum):
    """Relationship between local and provider values for one field."""

    UNRESOLVED = "unresolved"
    LOCAL_ONLY = "local_only"
    PROVIDER_ONLY = "provider_only"
    AGREEMENT = "agreement"
    PARTIAL_AGREEMENT = "partial_agreement"
    DIVERGENT = "divergent"


@dataclass(frozen=True, slots=True)
class MetadataFieldReconciliation:
    """Normalized comparison of one metadata field across evidence layers.

    Values are normalized comparison keys rather than replacements for the
    original provenance-bearing metadata values.
    """

    field: str
    status: MetadataFieldReconciliationStatus
    local_values: tuple[str, ...] = ()
    provider_values: tuple[str, ...] = ()
    agreement_values: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        field = self.field.strip().lower()

        if not field:
            raise ValueError("metadata reconciliation field must not be empty")

        object.__setattr__(
            self,
            "field",
            field,
        )

    @property
    def has_divergence(self) -> bool:
        """Whether both layers contain values with no agreement."""

        return self.status is MetadataFieldReconciliationStatus.DIVERGENT


@dataclass(frozen=True, slots=True)
class MetadataReconciliationReport:
    """Field-level comparison of local and provider metadata evidence."""

    fields: tuple[MetadataFieldReconciliation, ...]

    def __post_init__(self) -> None:
        names = tuple(field.field for field in self.fields)

        if len(set(names)) != len(names):
            raise ValueError("metadata reconciliation fields must be unique")

    @property
    def has_divergence(self) -> bool:
        """Whether any comparable field has fully divergent evidence."""

        return any(field.has_divergence for field in self.fields)

    def get(
        self,
        field_name: str,
    ) -> MetadataFieldReconciliation:
        """Return reconciliation for one comparable field."""

        normalized = field_name.strip().lower()

        for field in self.fields:
            if field.field == normalized:
                return field

        raise KeyError(normalized)


def _normalize_text(value: str) -> str:
    return " ".join(str(value).split()).casefold()


def _text_values(values: Sequence[object]) -> tuple[str, ...]:
    normalized = {
        _normalize_text(value.value) for value in values if _normalize_text(value.value)
    }

    return tuple(sorted(normalized))


def _player_count_values(
    values: Sequence[object],
) -> tuple[str, ...]:
    normalized = set()

    for value in values:
        context = _normalize_text(value.context) if value.context is not None else ""

        key = (
            f"{value.minimum}-{value.maximum}"
            if not context
            else (f"{value.minimum}-{value.maximum}@{context}")
        )

        normalized.add(key)

    return tuple(sorted(normalized))


def _local_values(
    local: LocalContentMetadata | None,
    field_name: str,
) -> tuple[str, ...]:
    if local is None:
        return ()

    values = getattr(local, field_name)

    if field_name == "player_counts":
        return _player_count_values(values)

    return _text_values(values)


def _provider_values(
    provider_results: Sequence[MetadataProviderResult],
    field_name: str,
) -> tuple[str, ...]:
    values = []

    for result in provider_results:
        values.extend(
            getattr(
                result.metadata,
                field_name,
            )
        )

    if field_name == "player_counts":
        return _player_count_values(values)

    return _text_values(values)


def _reconcile_values(
    field_name: str,
    local_values: tuple[str, ...],
    provider_values: tuple[str, ...],
) -> MetadataFieldReconciliation:
    local_set = set(local_values)
    provider_set = set(provider_values)

    if not local_set and not provider_set:
        status = MetadataFieldReconciliationStatus.UNRESOLVED
    elif local_set and not provider_set:
        status = MetadataFieldReconciliationStatus.LOCAL_ONLY
    elif provider_set and not local_set:
        status = MetadataFieldReconciliationStatus.PROVIDER_ONLY
    elif local_set == provider_set:
        status = MetadataFieldReconciliationStatus.AGREEMENT
    elif local_set & provider_set:
        status = MetadataFieldReconciliationStatus.PARTIAL_AGREEMENT
    else:
        status = MetadataFieldReconciliationStatus.DIVERGENT

    return MetadataFieldReconciliation(
        field=field_name,
        status=status,
        local_values=local_values,
        provider_values=provider_values,
        agreement_values=tuple(sorted(local_set & provider_set)),
    )


def reconcile_metadata(
    local: LocalContentMetadata | None,
    provider_results: Sequence[MetadataProviderResult],
) -> MetadataReconciliationReport:
    """Compare compatible local and provider metadata fields.

    This function reports relationships only. It does not select preferred
    values, mutate either evidence source, or assign verification meaning to
    metadata disagreement.
    """

    return MetadataReconciliationReport(
        fields=tuple(
            _reconcile_values(
                field_name,
                _local_values(
                    local,
                    field_name,
                ),
                _provider_values(
                    provider_results,
                    field_name,
                ),
            )
            for field_name in COMPARABLE_METADATA_FIELDS
        )
    )
