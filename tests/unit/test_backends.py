from pathlib import Path

import pytest

from rom_metadata_framework.backends import (
    BackendExecutionError,
    BackendSpec,
    BackendTimeoutError,
    BackendUnavailableError,
    discover_backend,
    probe_backend,
    run_backend,
)


def test_backend_spec_normalizes_names() -> None:
    spec = BackendSpec(
        name="  example ",
        executable=" python3 ",
    )

    assert spec.name == "example"
    assert spec.executable == "python3"


def test_backend_spec_rejects_empty_name() -> None:
    with pytest.raises(ValueError):
        BackendSpec(name=" ", executable="python3")


def test_backend_spec_rejects_empty_executable() -> None:
    with pytest.raises(ValueError):
        BackendSpec(name="example", executable=" ")


def test_discover_backend_reports_missing_executable() -> None:
    spec = BackendSpec(
        name="missing",
        executable="rom-metadata-framework-definitely-missing-command",
    )

    status = discover_backend(spec)

    assert status.available is False
    assert status.executable is None
    assert status.error is not None


def test_run_backend_rejects_missing_executable() -> None:
    spec = BackendSpec(
        name="missing",
        executable="rom-metadata-framework-definitely-missing-command",
    )

    with pytest.raises(BackendUnavailableError) as exc_info:
        run_backend(spec)

    error = exc_info.value

    assert error.backend_name == "missing"
    assert error.configured_executable == (
        "rom-metadata-framework-definitely-missing-command"
    )
    assert error.executable is None
    assert error.arguments == ()


def test_run_backend_captures_stdout() -> None:
    spec = BackendSpec(
        name="python",
        executable="python3",
    )

    result = run_backend(
        spec,
        ("-c", "print('backend-ok')"),
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "backend-ok"
    assert result.stderr == ""
    assert result.executable.is_absolute()


def test_run_backend_does_not_invoke_shell(tmp_path: Path) -> None:
    marker = tmp_path / "should-not-exist"

    spec = BackendSpec(
        name="python",
        executable="python3",
    )

    payload = f"touch {marker}"

    result = run_backend(
        spec,
        ("-c", "import sys; print(sys.argv[1])", payload),
    )

    assert result.stdout.strip() == payload
    assert not marker.exists()


def test_run_backend_reports_nonzero_exit() -> None:
    spec = BackendSpec(
        name="python",
        executable="python3",
    )

    with pytest.raises(BackendExecutionError) as exc_info:
        run_backend(
            spec,
            (
                "-c",
                (
                    "import sys; "
                    "print('stdout-text'); "
                    "print('stderr-text', file=sys.stderr); "
                    "raise SystemExit(7)"
                ),
            ),
        )

    error = exc_info.value

    assert error.backend_name == "python"
    assert error.configured_executable == "python3"
    assert error.executable is not None
    assert error.arguments[0] == "-c"
    assert error.returncode == 7
    assert "stdout-text" in error.stdout
    assert "stderr-text" in error.stderr


def test_run_backend_enforces_timeout() -> None:
    spec = BackendSpec(
        name="python",
        executable="python3",
    )

    with pytest.raises(BackendTimeoutError) as exc_info:
        run_backend(
            spec,
            ("-c", "import time; time.sleep(2)"),
            timeout=0.05,
        )

    error = exc_info.value

    assert error.backend_name == "python"
    assert error.configured_executable == "python3"
    assert error.executable is not None
    assert error.arguments == (
        "-c",
        "import time; time.sleep(2)",
    )
    assert error.timeout == 0.05


def test_probe_backend_captures_version() -> None:
    spec = BackendSpec(
        name="python",
        executable="python3",
        version_args=("--version",),
    )

    status = probe_backend(spec)

    assert status.available is True
    assert status.executable is not None
    assert status.version is not None
    assert "Python" in status.version


def test_backend_registry_registers_and_gets_specs() -> None:
    from rom_metadata_framework.backends import BackendRegistry

    registry = BackendRegistry()
    spec = BackendSpec(name="python", executable="python3")

    registry.register(spec)

    assert registry.get("python") is spec
    assert registry.names() == ("python",)


def test_backend_registry_rejects_duplicate_names() -> None:
    from rom_metadata_framework.backends import BackendRegistry

    registry = BackendRegistry()
    registry.register(BackendSpec(name="python", executable="python3"))

    with pytest.raises(ValueError):
        registry.register(
            BackendSpec(name="python", executable="different-python")
        )


def test_backend_registry_reports_unknown_name() -> None:
    from rom_metadata_framework.backends import BackendRegistry

    registry = BackendRegistry()

    with pytest.raises(KeyError):
        registry.get("missing")


def test_backend_registry_names_are_deterministic() -> None:
    from rom_metadata_framework.backends import BackendRegistry

    registry = BackendRegistry()

    registry.register(BackendSpec(name="zeta", executable="zeta"))
    registry.register(BackendSpec(name="alpha", executable="alpha"))

    assert registry.names() == ("alpha", "zeta")


def test_backend_registry_discovers_all() -> None:
    from rom_metadata_framework.backends import BackendRegistry

    registry = BackendRegistry()

    registry.register(
        BackendSpec(
            name="missing",
            executable="rom-metadata-framework-definitely-missing-command",
        )
    )
    registry.register(
        BackendSpec(
            name="python",
            executable="python3",
        )
    )

    statuses = registry.discover_all()

    assert tuple(statuses) == ("missing", "python")
    assert statuses["missing"].available is False
    assert statuses["python"].available is True


def test_probe_failure_preserves_backend_availability() -> None:
    spec = BackendSpec(
        name="python",
        executable="python3",
        version_args=("-c", "raise SystemExit(9)"),
    )

    status = probe_backend(spec)

    assert status.available is True
    assert status.executable is not None
    assert status.version is None
    assert status.error is not None



def test_backend_timeout_error_keeps_message_only_compatibility() -> None:
    error = BackendTimeoutError("backend timed out")

    assert str(error) == "backend timed out"
    assert error.backend_name is None
    assert error.configured_executable is None
    assert error.executable is None
    assert error.arguments == ()
    assert error.timeout is None


def test_backend_execution_error_keeps_existing_constructor() -> None:
    error = BackendExecutionError(
        executable="example-tool",
        returncode=9,
        stdout="output",
        stderr="error",
    )

    assert error.backend_name is None
    assert error.configured_executable is None
    assert error.executable == "example-tool"
    assert error.arguments == ()
    assert error.returncode == 9
    assert error.stdout == "output"
    assert error.stderr == "error"
