"""Report availability of the standard normalization runtime."""

from __future__ import annotations

from rom_metadata_framework.defaults import DefaultRuntimeConfig
from rom_metadata_framework.runtime import build_default_runtime_report


def main() -> int:
    report = build_default_runtime_report(DefaultRuntimeConfig())

    for capability in report.capabilities:
        print(f"{capability.name}: {capability.status.value}")

    print(f"fully ready: {report.fully_ready}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
