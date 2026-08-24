"""Identify one ROM or disc image with the standard framework composition."""

from __future__ import annotations

import argparse
from pathlib import Path

from rom_metadata_framework import (
    NamingPolicy,
    identify_file,
    verify_identification,
)
from rom_metadata_framework.defaults import (
    DefaultRuntimeConfig,
    build_default_detector,
    build_default_inspector,
    build_default_normalizer,
)
from rom_metadata_framework.playmatch import PlaymatchResolver


def identify_path(
    path: Path,
    *,
    config: DefaultRuntimeConfig | None = None,
):
    """Identify one path using the standard detector, inspector, and normalizer."""

    runtime_config = config or DefaultRuntimeConfig()

    return identify_file(
        path,
        detector=build_default_detector(runtime_config),
        resolver=PlaymatchResolver(),
        inspector=build_default_inspector(runtime_config),
        normalizer=build_default_normalizer(runtime_config),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()

    result = identify_path(args.path)

    print(f"physical file: {result.physical_identity.file_name}")
    print(f"identified: {result.identified}")

    if result.platform_detection.best is not None:
        print(f"detected platform: {result.platform_detection.best.platform}")

    if result.physical_representation is not None:
        print(f"representation: {result.physical_representation.format}")

    if result.local_metadata is not None:
        print("local metadata: available")

    canonical = result.canonical_match

    if canonical is None:
        print("canonical release: unresolved")
        return 0

    print(f"canonical release: {canonical.release_name}")
    print(f"canonical platform: {canonical.platform}")

    verification = verify_identification(result)
    print(f"safe for canonical naming: {verification.safe_for_canonical_naming}")

    plan = NamingPolicy().plan_identification_rename(
        args.path.name,
        result,
        verification=verification,
    )

    print(f"proposed filename: {plan.destination_name}")
    print(f"operation: {plan.operation}")
    print(f"safe to apply: {plan.safe_to_apply}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
