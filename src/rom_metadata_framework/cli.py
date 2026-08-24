from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .contracts import FrameworkContractError
from .defaults import (
    DefaultRuntimeConfig,
    build_default_detector,
    build_default_inspector,
    build_default_normalizer,
)
from .identification import identify_file
from .inspection import (
    AmbiguousStructuralInspectorError,
    StructuralInspectionResult,
)
from .platforms import platform_display_name
from .playmatch import (
    PlaymatchError,
    PlaymatchResolver,
)
from .runtime import build_default_runtime_report
from .support import platform_support_inventory
from .verification import (
    VerificationStatus,
    verify_release,
)

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_UNRESOLVED = 3
EXIT_CONFLICT = 4
EXIT_ERROR = 5


def _jsonable(value: Any) -> Any:
    """Convert framework result values into JSON-compatible data."""

    if value is None:
        return None

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, Path):
        return str(value)

    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _jsonable(
                getattr(value, field.name)
            )
            for field in fields(value)
        }

    if isinstance(value, Mapping):
        return {
            str(key): _jsonable(item)
            for key, item in value.items()
        }

    if isinstance(value, (tuple, list)):
        return [
            _jsonable(item)
            for item in value
        ]

    if isinstance(value, (str, int, float, bool)):
        return value

    return str(value)



def _hashes_payload(value: object | None) -> object | None:
    if value is None:
        return None

    return {
        "crc32": getattr(value, "crc32", None),
        "md5": getattr(value, "md5", None),
        "sha1": getattr(value, "sha1", None),
        "sha256": getattr(value, "sha256", None),
    }


def _adapter_payload(value: object | None) -> object | None:
    if value is None:
        return None

    return {
        "name": getattr(value, "name", None),
        "version": getattr(value, "version", None),
        "backend": getattr(value, "backend", None),
    }


def _rom_identity_payload(
    value: object | None,
) -> object | None:
    if value is None:
        return None

    return {
        "platform": getattr(value, "platform", None),
        "format": getattr(value, "format", None),
        "file_name": getattr(value, "file_name", None),
        "file_size": getattr(value, "file_size", None),
        "hashes": _hashes_payload(
            getattr(value, "hashes", None)
        ),
        "serial": getattr(value, "serial", None),
        "product_code": getattr(
            value,
            "product_code",
            None,
        ),
        "title_id": getattr(value, "title_id", None),
        "specialized_identifiers": dict(
            getattr(
                value,
                "specialized_identifiers",
                {},
            )
        ),
        "media_metadata": dict(
            getattr(
                value,
                "media_metadata",
                {},
            )
        ),
        "adapter": _adapter_payload(
            getattr(value, "adapter", None)
        ),
    }


def _platform_evidence_payload(
    value: object,
) -> dict[str, object]:
    return {
        "source": getattr(value, "source", None),
        "method": getattr(value, "method", None),
        "value": getattr(value, "value", None),
        "strength": getattr(value, "strength", None),
        "details": dict(
            getattr(value, "details", {})
        ),
    }


def _platform_candidate_payload(
    value: object,
) -> dict[str, object]:
    return {
        "platform": getattr(value, "platform", None),
        "confidence": getattr(
            value,
            "confidence",
            None,
        ),
        "evidence": [
            _platform_evidence_payload(item)
            for item in getattr(
                value,
                "evidence",
                (),
            )
        ],
    }


def _platform_detection_payload(
    value: object | None,
) -> object | None:
    if value is None:
        return None

    return {
        "candidates": [
            _platform_candidate_payload(item)
            for item in getattr(
                value,
                "candidates",
                (),
            )
        ],
    }


def _representation_payload(
    value: object | None,
) -> object | None:
    if value is None:
        return None

    return {
        "kind": getattr(value, "kind", None),
        "format": getattr(value, "format", None),
        "metadata": dict(
            getattr(value, "metadata", {})
        ),
    }


def _local_provenance_payload(
    value: object | None,
) -> object | None:
    if value is None:
        return None

    return {
        "source": getattr(value, "source", None),
        "method": getattr(value, "method", None),
        "raw_value": getattr(
            value,
            "raw_value",
            None,
        ),
        "details": dict(
            getattr(value, "details", {})
        ),
    }


def _local_value_payload(
    value: object,
) -> dict[str, object]:
    return {
        "value": _jsonable(
            getattr(value, "value", None)
        ),
        "provenance": _local_provenance_payload(
            getattr(
                value,
                "provenance",
                None,
            )
        ),
    }


def _local_identifier_payload(
    value: object,
) -> dict[str, object]:
    return {
        "namespace": getattr(
            value,
            "namespace",
            None,
        ),
        "value": getattr(value, "value", None),
        "provenance": _local_provenance_payload(
            getattr(
                value,
                "provenance",
                None,
            )
        ),
    }


def _local_timestamp_payload(
    value: object,
) -> dict[str, object]:
    timestamp = getattr(
        value,
        "value",
        None,
    )

    return {
        "kind": getattr(value, "kind", None),
        "value": (
            timestamp.isoformat()
            if hasattr(timestamp, "isoformat")
            else _jsonable(timestamp)
        ),
        "provenance": _local_provenance_payload(
            getattr(
                value,
                "provenance",
                None,
            )
        ),
    }


def _local_player_count_payload(
    value: object,
) -> dict[str, object]:
    return {
        "minimum": getattr(
            value,
            "minimum",
            None,
        ),
        "maximum": getattr(
            value,
            "maximum",
            None,
        ),
        "provenance": _local_provenance_payload(
            getattr(
                value,
                "provenance",
                None,
            )
        ),
        "context": getattr(
            value,
            "context",
            None,
        ),
    }


def _local_metadata_payload(
    value: object | None,
) -> object | None:
    if value is None:
        return None

    value_fields = (
        "titles",
        "short_titles",
        "release_revisions",
        "software_versions",
        "executable_versions",
        "disc_numbers",
        "disc_totals",
        "regions",
        "countries",
        "languages",
        "developers",
        "publishers",
        "manufacturers",
        "maker_codes",
        "ratings",
        "multiplayer_features",
    )

    payload: dict[str, object] = {
        "platform": getattr(
            value,
            "platform",
            None,
        ),
        "identifiers": [
            _local_identifier_payload(item)
            for item in getattr(
                value,
                "identifiers",
                (),
            )
        ],
        "timestamps": [
            _local_timestamp_payload(item)
            for item in getattr(
                value,
                "timestamps",
                (),
            )
        ],
        "player_counts": [
            _local_player_count_payload(item)
            for item in getattr(
                value,
                "player_counts",
                (),
            )
        ],
        "hardware": dict(
            getattr(value, "hardware", {})
        ),
        "media": dict(
            getattr(value, "media", {})
        ),
        "boot": dict(
            getattr(value, "boot", {})
        ),
        "native_metadata": dict(
            getattr(
                value,
                "native_metadata",
                {},
            )
        ),
    }

    for name in value_fields:
        payload[name] = [
            _local_value_payload(item)
            for item in getattr(
                value,
                name,
                (),
            )
        ]

    return payload


def _normalized_content_payload(
    value: object | None,
) -> object | None:
    if value is None:
        return None

    return {
        "kind": getattr(value, "kind", None),
        "hashes": _hashes_payload(
            getattr(value, "hashes", None)
        ),
        "specialized_identifiers": dict(
            getattr(
                value,
                "specialized_identifiers",
                {},
            )
        ),
        "metadata": dict(
            getattr(value, "metadata", {})
        ),
    }


def _identity_evidence_payload(
    value: object,
) -> dict[str, object]:
    return {
        "source": getattr(value, "source", None),
        "method": getattr(value, "method", None),
        "authoritative": bool(
            getattr(
                value,
                "authoritative",
                False,
            )
        ),
        "value": getattr(value, "value", None),
        "details": dict(
            getattr(value, "details", {})
        ),
    }


def _catalogue_evidence_payload(
    value: object,
) -> dict[str, object]:
    return {
        "source": getattr(value, "source", None),
        "match_method": getattr(
            value,
            "match_method",
            None,
        ),
        "authority": getattr(
            value,
            "authority",
            None,
        ),
        "catalogue_name": getattr(
            value,
            "catalogue_name",
            None,
        ),
        "catalogue_version": getattr(
            value,
            "catalogue_version",
            None,
        ),
        "import_version": getattr(
            value,
            "import_version",
            None,
        ),
        "file_status": getattr(
            value,
            "file_status",
            None,
        ),
        "current_in_latest_catalogue": getattr(
            value,
            "current_in_latest_catalogue",
            None,
        ),
        "matched_file_name": getattr(
            value,
            "matched_file_name",
            None,
        ),
        "hashes": dict(
            getattr(value, "hashes", {})
        ),
        "details": dict(
            getattr(value, "details", {})
        ),
    }


def _canonical_release_payload(
    value: object | None,
) -> object | None:
    if value is None:
        return None

    return {
        "release_name": getattr(
            value,
            "release_name",
            None,
        ),
        "platform": getattr(
            value,
            "platform",
            None,
        ),
        "source": getattr(value, "source", None),
        "source_id": getattr(
            value,
            "source_id",
            None,
        ),
        "title": getattr(value, "title", None),
        "external_ids": dict(
            getattr(
                value,
                "external_ids",
                {},
            )
        ),
        "evidence": [
            _identity_evidence_payload(item)
            for item in getattr(
                value,
                "evidence",
                (),
            )
        ],
        "catalogue_evidence": [
            _catalogue_evidence_payload(item)
            for item in getattr(
                value,
                "catalogue_evidence",
                (),
            )
        ],
        "conflicts": list(
            getattr(value, "conflicts", ())
        ),
    }


def _release_reconciliation_payload(
    value: object | None,
) -> object | None:
    if value is None:
        return None

    status = getattr(value, "status", None)

    return {
        "status": _jsonable(status),
        "selected": _canonical_release_payload(
            getattr(value, "selected", None)
        ),
        "physical": _canonical_release_payload(
            getattr(value, "physical", None)
        ),
        "normalized": _canonical_release_payload(
            getattr(value, "normalized", None)
        ),
        "conflicts": list(
            getattr(value, "conflicts", ())
        ),
    }


def _platform_reconciliation_payload(
    value: object | None,
) -> object | None:
    if value is None:
        return None

    return {
        "status": _jsonable(
            getattr(value, "status", None)
        ),
        "selected_platform": getattr(
            value,
            "selected_platform",
            None,
        ),
        "local_platform": getattr(
            value,
            "local_platform",
            None,
        ),
        "provider_platform": getattr(
            value,
            "provider_platform",
            None,
        ),
        "conflicts": list(
            getattr(value, "conflicts", ())
        ),
    }


def _inspection_result_payload(
    value: object | None,
) -> object | None:
    if value is None:
        return None

    return {
        "physical_representation": (
            _representation_payload(
                getattr(
                    value,
                    "physical_representation",
                    None,
                )
            )
        ),
        "local_metadata": _local_metadata_payload(
            getattr(
                value,
                "local_metadata",
                None,
            )
        ),
    }


def _verification_report_payload(
    value: object | None,
) -> object | None:
    if value is None:
        return None

    return {
        "status": _jsonable(
            getattr(value, "status", None)
        ),
        "evidence": [
            _catalogue_evidence_payload(item)
            for item in getattr(
                value,
                "evidence",
                (),
            )
        ],
        "reasons": list(
            getattr(value, "reasons", ())
        ),
        "conflicts": list(
            getattr(value, "conflicts", ())
        ),
    }



def _emit_json(payload: object) -> None:
    print(
        json.dumps(
            _jsonable(payload),
            indent=2,
            sort_keys=True,
        )
    )


def _platforms_payload() -> list[dict[str, object]]:
    return [
        {
            "platform": item.platform,
            "display_name": item.display_name,
            "manufacturer": item.manufacturer,
            "status": item.status.value,
            "detection": item.detection.value,
            "inspection": item.inspection.value,
            "normalization": item.normalization.value,
            "integrity": item.integrity.value,
            "normalization_backend": (
                item.normalization_backend
            ),
            "rcheevos_mapping": item.rcheevos_mapping,
            "notes": list(item.notes),
        }
        for item in platform_support_inventory()
    ]


def _print_platforms(*, as_json: bool) -> int:
    payload = _platforms_payload()

    if as_json:
        _emit_json(payload)
        return EXIT_OK

    header = (
        "PLATFORM\tDISPLAY_NAME\tMANUFACTURER"
        "\tSTATUS\tDETECT\tINSPECT\tNORMALIZE"
        "\tINTEGRITY\tRCHEEVOS_MAP"
    )
    print(header)

    for item in payload:
        print(
            "\t".join(
                (
                    str(item["platform"]),
                    str(item["display_name"]),
                    str(item["manufacturer"]),
                    str(item["status"]),
                    str(item["detection"]),
                    str(item["inspection"]),
                    str(item["normalization"]),
                    str(item["integrity"]),
                    (
                        "yes"
                        if item["rcheevos_mapping"]
                        else "no"
                    ),
                )
            )
        )

    return EXIT_OK


def _capabilities_payload() -> list[dict[str, object]]:
    report = build_default_runtime_report(
        DefaultRuntimeConfig()
    )

    return [
        {
            "name": capability.name,
            "status": capability.status.value,
            "backend": capability.backend,
            "version": capability.version,
            "reason": capability.reason,
            "details": dict(capability.details),
        }
        for capability in report.capabilities
    ]


def _print_capabilities(*, as_json: bool) -> int:
    payload = _capabilities_payload()

    if as_json:
        _emit_json(payload)
        return EXIT_OK

    for item in payload:
        line = (
            f"{item['name']}: "
            f"{item['status']}"
        )

        if item["backend"]:
            line += (
                f" [{item['backend']}]"
            )

        if item["version"]:
            line += (
                f" {item['version']}"
            )

        if item["reason"]:
            line += (
                f" - {item['reason']}"
            )

        print(line)

    return EXIT_OK


def _inspection_payload(
    path: Path,
    *,
    detection: object,
    inspection: StructuralInspectionResult | None,
) -> dict[str, object]:
    best = getattr(detection, "best", None)

    return {
        "path": str(path),
        "detected_platform": (
            getattr(best, "platform", None)
            if best is not None
            else None
        ),
        "platform_detection": (
            _platform_detection_payload(detection)
        ),
        "inspection": _inspection_result_payload(
            inspection
        ),
    }


def _print_inspection_text(
    payload: Mapping[str, object],
) -> None:
    print(f"path: {payload['path']}")

    detected = payload["detected_platform"]

    if detected is None:
        print("detected platform: unresolved")
    else:
        print(f"detected platform: {detected}")

    inspection = payload["inspection"]

    if not isinstance(inspection, Mapping):
        print("structural inspection: unavailable")
        return

    print("structural inspection: available")

    representation = inspection.get(
        "physical_representation"
    )

    if isinstance(representation, Mapping):
        representation_format = representation.get(
            "format"
        )

        if representation_format is not None:
            print(
                "representation: "
                f"{representation_format}"
            )

    local_metadata = inspection.get(
        "local_metadata"
    )

    print(
        "local metadata: "
        + (
            "available"
            if local_metadata is not None
            else "unavailable"
        )
    )


def _inspect_path(
    path: Path,
    *,
    as_json: bool,
) -> int:
    path = Path(path)

    if not path.exists():
        print(
            f"error: path does not exist: {path}",
            file=sys.stderr,
        )
        return EXIT_ERROR

    if not path.is_file():
        print(
            f"error: path is not a regular file: {path}",
            file=sys.stderr,
        )
        return EXIT_ERROR

    config = DefaultRuntimeConfig()
    detector = build_default_detector(config)
    inspector = build_default_inspector(config)

    try:
        detection = detector.detect(path)
        inspection = inspector.inspect(path)
    except AmbiguousStructuralInspectorError as exc:
        payload = {
            "path": str(path),
            "error": "ambiguous-structural-inspection",
            "inspectors": list(exc.inspector_names),
        }

        if as_json:
            _emit_json(payload)
        else:
            print(
                "structural inspection conflict: "
                + ", ".join(exc.inspector_names),
                file=sys.stderr,
            )

        return EXIT_CONFLICT
    except OSError as exc:
        payload = {
            "path": str(path),
            "error": "io-error",
            "message": str(exc),
        }

        if as_json:
            _emit_json(payload)
        else:
            print(
                f"error: {exc}",
                file=sys.stderr,
            )

        return EXIT_ERROR

    payload = _inspection_payload(
        path,
        detection=detection,
        inspection=inspection,
    )

    if as_json:
        _emit_json(payload)
    else:
        _print_inspection_text(payload)

    if inspection is None:
        return EXIT_UNRESOLVED

    return EXIT_OK



_PRIMARY_IDENTIFIER_PRESENTATION = {
    "gc": (
        "nintendo-game-id",
        "Game ID",
    ),
    "wii": (
        "nintendo-game-id",
        "Game ID",
    ),
    "ps2": (
        "ps2-product-code",
        "Product Code",
    ),
    "ps3": (
        "ps3-title-id",
        "Title ID",
    ),
    "xbox": (
        "xbox-title-id",
        "Title ID",
    ),
    "xbox360": (
        "xbox360-title-id",
        "Title ID",
    ),
    "switch": (
        "switch-application-id",
        "Application ID",
    ),
}


def _nonempty_hashes_payload(
    value: object | None,
) -> dict[str, str]:
    """Project only available standard hashes."""

    if value is None:
        return {}

    payload = {}

    for name in (
        "crc32",
        "md5",
        "sha1",
        "sha256",
    ):
        item = getattr(
            value,
            name,
            None,
        )

        if item is not None:
            payload[name] = str(item)

    return payload


def _first_local_value(
    metadata: object | None,
    field: str,
) -> object | None:
    """Return the first represented local metadata value."""

    if metadata is None:
        return None

    values = getattr(
        metadata,
        field,
        (),
    )

    if not values:
        return None

    return getattr(
        values[0],
        "value",
        None,
    )


def _concise_platform(
    result: object,
) -> tuple[str | None, str | None]:
    """Return canonical and human-readable platform names."""

    canonical = getattr(
        result,
        "canonical_match",
        None,
    )
    local_metadata = getattr(
        result,
        "local_metadata",
        None,
    )
    detection = getattr(
        result,
        "platform_detection",
        None,
    )
    best = getattr(
        detection,
        "best",
        None,
    )

    platform = (
        getattr(
            canonical,
            "platform",
            None,
        )
        if canonical is not None
        else None
    )

    if platform is None and local_metadata is not None:
        platform = getattr(
            local_metadata,
            "platform",
            None,
        )

    if platform is None and best is not None:
        platform = getattr(
            best,
            "platform",
            None,
        )

    if platform is None:
        return None, None

    try:
        display = platform_display_name(
            str(platform)
        )
    except ValueError:
        display = str(platform)

    return str(platform), display


def _concise_primary_identifier(
    result: object,
    *,
    platform: str | None,
) -> dict[str, str] | None:
    """Select the preferred platform-native identifier."""

    if platform is None:
        return None

    presentation = _PRIMARY_IDENTIFIER_PRESENTATION.get(
        platform
    )

    if presentation is None:
        return None

    namespace, label = presentation

    metadata = getattr(
        result,
        "local_metadata",
        None,
    )

    if metadata is None:
        return None

    for identifier in getattr(
        metadata,
        "identifiers",
        (),
    ):
        if (
            getattr(
                identifier,
                "namespace",
                None,
            )
            == namespace
        ):
            value = getattr(
                identifier,
                "value",
                None,
            )

            if value is None:
                return None

            return {
                "type": namespace,
                "label": label,
                "value": str(value),
            }

    return None


def _concise_disc(
    metadata: object | None,
) -> dict[str, int] | None:
    """Return disc position only for known multi-disc releases."""

    number = _first_local_value(
        metadata,
        "disc_numbers",
    )
    total = _first_local_value(
        metadata,
        "disc_totals",
    )

    if (
        isinstance(number, bool)
        or not isinstance(number, int)
        or isinstance(total, bool)
        or not isinstance(total, int)
        or total <= 1
    ):
        return None

    return {
        "number": number,
        "total": total,
    }


def _concise_identification_payload(
    path: Path,
    result: object,
) -> dict[str, object]:
    """Build the normal compact identification result."""

    canonical = getattr(
        result,
        "canonical_match",
        None,
    )
    metadata = getattr(
        result,
        "local_metadata",
        None,
    )

    title = getattr(
        result,
        "display_title",
        None,
    )

    if title is None and canonical is not None:
        title = (
            getattr(
                canonical,
                "title",
                None,
            )
            or getattr(
                canonical,
                "release_name",
                None,
            )
        )

    if title is None:
        title = _first_local_value(
            metadata,
            "titles",
        )

    platform, platform_name = _concise_platform(
        result
    )

    strength = getattr(
        result,
        "identification_strength",
        None,
    )
    status = _jsonable(strength)

    if status is None:
        status = (
            "catalogue"
            if canonical is not None
            else "unresolved"
        )

    title_source = _jsonable(
        getattr(
            result,
            "title_source",
            None,
        )
    )

    if title_source is None:
        if canonical is not None:
            title_source = "catalogue"
        elif title is not None:
            title_source = "embedded"

    representation = getattr(
        result,
        "physical_representation",
        None,
    )

    source_format = (
        path.suffix.lower().lstrip(".")
        or None
    )

    representation_format = getattr(
        representation,
        "format",
        None,
    )

    format_name = (
        source_format
        or representation_format
    )

    region = _first_local_value(
        metadata,
        "countries",
    )

    if region is None:
        region = _first_local_value(
            metadata,
            "regions",
        )

    revision = _first_local_value(
        metadata,
        "release_revisions",
    )

    if revision is not None:
        revision = str(revision)

        if revision.strip().lower() in {
            "",
            "0",
            "rev 0",
            "revision 0",
        }:
            revision = None

    payload: dict[str, object] = {
        "path": str(path),
        "status": status,
    }

    if title is not None:
        payload["title"] = str(title)

    if title_source is not None:
        payload["title_source"] = title_source

    if platform is not None:
        platform_payload = {
            "id": platform,
        }

        if platform_name is not None:
            platform_payload["name"] = platform_name

        payload["platform"] = platform_payload

    if region is not None:
        payload["region"] = str(region)

    identifier = _concise_primary_identifier(
        result,
        platform=platform,
    )

    if identifier is not None:
        payload["identifier"] = identifier

    if revision is not None:
        payload["revision"] = revision

    disc = _concise_disc(metadata)

    if disc is not None:
        payload["disc"] = disc

    if format_name is not None:
        payload["format"] = str(format_name)

    physical_identity = getattr(
        result,
        "physical_identity",
        None,
    )
    physical_hashes = _nonempty_hashes_payload(
        getattr(
            physical_identity,
            "hashes",
            None,
        )
    )

    normalized_content = getattr(
        result,
        "normalized_content",
        None,
    )
    normalized_hashes = _nonempty_hashes_payload(
        getattr(
            normalized_content,
            "hashes",
            None,
        )
    )

    hashes = {}

    if physical_hashes:
        hashes["physical"] = physical_hashes

    if normalized_hashes:
        hashes["disc"] = normalized_hashes

    if hashes:
        payload["hashes"] = hashes

    provider_name = getattr(
        result,
        "provider_name",
        None,
    )

    physical_lookup = getattr(
        result,
        "physical_lookup",
        None,
    )
    normalized_lookup = getattr(
        result,
        "normalized_lookup",
        None,
    )

    provider = {}

    if provider_name is not None:
        provider["name"] = str(provider_name)

    physical_status = _jsonable(
        getattr(
            physical_lookup,
            "status",
            None,
        )
    )
    normalized_status = _jsonable(
        getattr(
            normalized_lookup,
            "status",
            None,
        )
    )

    if physical_status is not None:
        provider["physical"] = physical_status

    if normalized_status is not None:
        provider["normalized"] = normalized_status

    if provider:
        payload["provider"] = provider

    return payload


def _identification_payload(
    path: Path,
    result: object,
) -> dict[str, object]:
    """Build the stable CLI representation of an identification result."""

    canonical = getattr(
        result,
        "canonical_match",
        None,
    )

    platform_detection = getattr(
        result,
        "platform_detection",
        None,
    )
    best = getattr(
        platform_detection,
        "best",
        None,
    )

    return {
        "path": str(path),
        "identified": bool(
            getattr(
                result,
                "identified",
                False,
            )
        ),
        "detected_platform": (
            getattr(
                best,
                "platform",
                None,
            )
            if best is not None
            else None
        ),
        "physical_identity": _rom_identity_payload(
            getattr(
                result,
                "physical_identity",
                None,
            )
        ),
        "platform_detection": (
            _platform_detection_payload(
                platform_detection
            )
        ),
        "physical_match": _canonical_release_payload(
            getattr(
                result,
                "physical_match",
                None,
            )
        ),
        "physical_representation": (
            _representation_payload(
                getattr(
                    result,
                    "physical_representation",
                    None,
                )
            )
        ),
        "local_metadata": _local_metadata_payload(
            getattr(
                result,
                "local_metadata",
                None,
            )
        ),
        "normalized_content": (
            _normalized_content_payload(
                getattr(
                    result,
                    "normalized_content",
                    None,
                )
            )
        ),
        "normalized_match": _canonical_release_payload(
            getattr(
                result,
                "normalized_match",
                None,
            )
        ),
        "release_reconciliation": (
            _release_reconciliation_payload(
                getattr(
                    result,
                    "release_reconciliation",
                    None,
                )
            )
        ),
        "platform_reconciliation": (
            _platform_reconciliation_payload(
                getattr(
                    result,
                    "platform_reconciliation",
                    None,
                )
            )
        ),
        "canonical_match": (
            _canonical_release_payload(
                canonical
            )
        ),
    }


def _print_identification_text(
    payload: Mapping[str, object],
    *,
    include_hashes: bool = False,
) -> None:
    """Render concise human-readable identification output."""

    rows = []

    title = payload.get("title")

    if title is not None:
        rows.append(
            (
                "Title",
                str(title),
            )
        )

    platform = payload.get("platform")

    if isinstance(platform, Mapping):
        platform_name = (
            platform.get("name")
            or platform.get("id")
        )

        if platform_name is not None:
            rows.append(
                (
                    "Platform",
                    str(platform_name),
                )
            )

    region = payload.get("region")

    if region is not None:
        rows.append(
            (
                "Region",
                str(region),
            )
        )

    identifier = payload.get("identifier")

    if isinstance(identifier, Mapping):
        label = identifier.get(
            "label",
            "Identifier",
        )
        value = identifier.get("value")

        if value is not None:
            rows.append(
                (
                    str(label),
                    str(value),
                )
            )

    revision = payload.get("revision")

    if revision is not None:
        rows.append(
            (
                "Revision",
                str(revision),
            )
        )

    disc = payload.get("disc")

    if isinstance(disc, Mapping):
        number = disc.get("number")
        total = disc.get("total")

        if number is not None and total is not None:
            rows.append(
                (
                    "Disc",
                    f"{number} / {total}",
                )
            )

    format_name = payload.get("format")

    if format_name is not None:
        rows.append(
            (
                "Format",
                str(format_name).upper(),
            )
        )

    if not rows:
        print("Unresolved")
    else:
        width = max(
            len(label)
            for label, _ in rows
        )

        for label, value in rows:
            print(
                f"{label + ':':<{width + 2}} {value}"
            )

    if not include_hashes:
        return

    hashes = payload.get("hashes")

    if not isinstance(hashes, Mapping):
        return

    physical = hashes.get("physical")

    if isinstance(physical, Mapping) and physical:
        print()
        print("Physical file hashes:")

        for name in (
            "crc32",
            "md5",
            "sha1",
            "sha256",
        ):
            value = physical.get(name)

            if value is not None:
                print(
                    f"  {name.upper()}: {value}"
                )

    disc_hashes = hashes.get("disc")

    if isinstance(disc_hashes, Mapping) and disc_hashes:
        print()
        print("Disc hashes:")

        for name in (
            "crc32",
            "md5",
            "sha1",
            "sha256",
        ):
            value = disc_hashes.get(name)

            if value is not None:
                print(
                    f"  {name.upper()}: {value}"
                )


def _run_identification_workflow(
    path: Path,
    *,
    as_json: bool,
    normalize: bool,
    conflict_context: str,
) -> tuple[object | None, int | None]:
    """Run the shared full identification workflow for CLI commands."""

    path = Path(path)

    if not path.exists():
        print(
            f"error: path does not exist: {path}",
            file=sys.stderr,
        )
        return None, EXIT_ERROR

    if not path.is_file():
        print(
            f"error: path is not a regular file: {path}",
            file=sys.stderr,
        )
        return None, EXIT_ERROR

    config = DefaultRuntimeConfig()

    try:
        result = identify_file(
            path,
            detector=build_default_detector(
                config
            ),
            resolver=PlaymatchResolver(),
            inspector=build_default_inspector(
                config
            ),
            normalizer=(
                build_default_normalizer(
                    config
                )
                if normalize
                else None
            ),
        )
    except AmbiguousStructuralInspectorError as exc:
        payload = {
            "path": str(path),
            "error": "ambiguous-structural-inspection",
            "inspectors": list(
                exc.inspector_names
            ),
        }

        if as_json:
            _emit_json(payload)
        else:
            print(
                f"{conflict_context} conflict: "
                + ", ".join(
                    exc.inspector_names
                ),
                file=sys.stderr,
            )

        return None, EXIT_CONFLICT
    except PlaymatchError as exc:
        payload = {
            "path": str(path),
            "error": "provider-error",
            "provider": "playmatch",
            "message": str(exc),
        }

        if as_json:
            _emit_json(payload)
        else:
            print(
                f"Playmatch error: {exc}",
                file=sys.stderr,
            )

        return None, EXIT_ERROR
    except FrameworkContractError as exc:
        payload = {
            "path": str(path),
            "error": "framework-contract-error",
            "message": str(exc),
        }

        if as_json:
            _emit_json(payload)
        else:
            print(
                f"framework error: {exc}",
                file=sys.stderr,
            )

        return None, EXIT_ERROR
    except OSError as exc:
        payload = {
            "path": str(path),
            "error": "io-error",
            "message": str(exc),
        }

        if as_json:
            _emit_json(payload)
        else:
            print(
                f"error: {exc}",
                file=sys.stderr,
            )

        return None, EXIT_ERROR

    return result, None


def _identify_path(
    path: Path,
    *,
    as_json: bool,
    normalize: bool,
    complete: bool = False,
    include_hashes: bool = False,
) -> int:
    """Run the complete hashing/provider identification workflow."""

    result, error_code = _run_identification_workflow(
        path,
        as_json=as_json,
        normalize=normalize,
        conflict_context="identification",
    )

    if error_code is not None:
        return error_code

    assert result is not None

    concise_payload = _concise_identification_payload(
        path,
        result,
    )

    if as_json:
        payload = (
            _identification_payload(
                path,
                result,
            )
            if complete
            else concise_payload
        )

        _emit_json(payload)
    else:
        _print_identification_text(
            concise_payload,
            include_hashes=include_hashes,
        )

    if (
        bool(
            getattr(
                result,
                "has_release_conflict",
                False,
            )
        )
        or bool(
            getattr(
                result,
                "has_platform_conflict",
                False,
            )
        )
    ):
        return EXIT_CONFLICT

    strength = _jsonable(
        getattr(
            result,
            "identification_strength",
            None,
        )
    )

    if strength in {
        "catalogue",
        "local_strong",
    }:
        return EXIT_OK

    if strength is None and bool(
        getattr(
            result,
            "identified",
            False,
        )
    ):
        return EXIT_OK

    return EXIT_UNRESOLVED



def _verification_payload(
    path: Path,
    *,
    identification: object,
    report: object | None,
) -> dict[str, object]:
    canonical = getattr(
        identification,
        "canonical_match",
        None,
    )

    return {
        "path": str(path),
        "canonical_match": (
            _canonical_release_payload(
                canonical
            )
        ),
        "verification": (
            _verification_report_payload(
                report
            )
        ),
    }


def _print_verification_text(
    payload: Mapping[str, object],
) -> None:
    print(f"path: {payload['path']}")

    canonical = payload["canonical_match"]

    if isinstance(canonical, Mapping):
        print(
            "canonical release: "
            + str(
                canonical.get(
                    "release_name",
                    "resolved",
                )
            )
        )
    else:
        print("canonical release: unresolved")

    verification = payload["verification"]

    if not isinstance(
        verification,
        Mapping,
    ):
        print("verification: unavailable")
        return

    print(
        "verification: "
        + str(
            verification.get(
                "status",
                "unknown",
            )
        )
    )

    reasons = verification.get(
        "reasons",
        [],
    )

    if isinstance(reasons, list):
        for reason in reasons:
            print(f"reason: {reason}")

    conflicts = verification.get(
        "conflicts",
        [],
    )

    if isinstance(conflicts, list):
        for conflict in conflicts:
            print(f"conflict: {conflict}")


def _verify_path(
    path: Path,
    *,
    as_json: bool,
    normalize: bool,
) -> int:
    """Identify and conservatively verify a release."""

    result, error_code = _run_identification_workflow(
        path,
        as_json=as_json,
        normalize=normalize,
        conflict_context="verification",
    )

    if error_code is not None:
        return error_code

    assert result is not None

    canonical = getattr(
        result,
        "canonical_match",
        None,
    )

    if canonical is None:
        payload = _verification_payload(
            path,
            identification=result,
            report=None,
        )

        if as_json:
            _emit_json(payload)
        else:
            _print_verification_text(
                payload
            )

        return EXIT_UNRESOLVED

    report = verify_release(
        canonical
    )

    payload = _verification_payload(
        path,
        identification=result,
        report=report,
    )

    if as_json:
        _emit_json(payload)
    else:
        _print_verification_text(
            payload
        )

    if report.status is VerificationStatus.KNOWN_GOOD:
        return EXIT_OK

    if report.status in {
        VerificationStatus.KNOWN_BAD,
        VerificationStatus.CONFLICT,
    }:
        return EXIT_CONFLICT

    return EXIT_UNRESOLVED



def build_parser() -> argparse.ArgumentParser:
    """Build the public command-line parser."""

    parser = argparse.ArgumentParser(
        prog="rom-metadata",
        description=(
            "Inspect ROM metadata framework support, "
            "runtime capabilities, and local structures."
        ),
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    platforms = subparsers.add_parser(
        "platforms",
        help="show registered platform support",
    )
    platforms.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit machine-readable JSON",
    )

    capabilities = subparsers.add_parser(
        "capabilities",
        help="show optional runtime backend state",
    )
    capabilities.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit machine-readable JSON",
    )

    inspect = subparsers.add_parser(
        "inspect",
        help=(
            "perform bounded local platform detection "
            "and structural inspection"
        ),
    )
    inspect.add_argument(
        "path",
        type=Path,
        help="ROM, package, or disc-image path",
    )
    inspect.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit machine-readable JSON",
    )

    identify = subparsers.add_parser(
        "identify",
        help=(
            "hash a file and resolve its release through "
            "the standard Playmatch workflow"
        ),
    )
    identify.add_argument(
        "path",
        type=Path,
        help="ROM, package, or disc-image path",
    )
    identify.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit machine-readable JSON",
    )
    identify.add_argument(
        "--no-normalize",
        action="store_true",
        help=(
            "skip canonical-content normalization "
            "and normalized provider lookup"
        ),
    )
    identify.add_argument(
        "--hashes",
        action="store_true",
        help=(
            "show available physical-file and "
            "represented-content hashes in text output"
        ),
    )
    identify.add_argument(
        "--complete",
        action="store_true",
        help=(
            "emit the complete diagnostic identification "
            "payload when used with --json"
        ),
    )

    verify = subparsers.add_parser(
        "verify",
        help=(
            "identify a file and assess catalogue-backed "
            "verification evidence"
        ),
    )
    verify.add_argument(
        "path",
        type=Path,
        help="ROM, package, or disc-image path",
    )
    verify.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="emit machine-readable JSON",
    )
    verify.add_argument(
        "--no-normalize",
        action="store_true",
        help=(
            "skip canonical-content normalization "
            "and normalized provider lookup"
        ),
    )

    return parser


def main(
    argv: Sequence[str] | None = None,
) -> int:
    """Run the public CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "platforms":
        return _print_platforms(
            as_json=args.as_json
        )

    if args.command == "capabilities":
        return _print_capabilities(
            as_json=args.as_json
        )

    if args.command == "inspect":
        return _inspect_path(
            args.path,
            as_json=args.as_json,
        )

    if args.command == "identify":
        if args.complete and not args.as_json:
            parser.error(
                "--complete requires --json"
            )

        return _identify_path(
            args.path,
            as_json=args.as_json,
            normalize=not args.no_normalize,
            complete=args.complete,
            include_hashes=args.hashes,
        )

    if args.command == "verify":
        return _verify_path(
            args.path,
            as_json=args.as_json,
            normalize=not args.no_normalize,
        )

    parser.error(
        f"unsupported command: {args.command}"
    )
    return EXIT_USAGE
