from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TIMEOUT_SECONDS = 30.0


class BackendError(RuntimeError):
    """Base exception for external backend failures."""


class BackendUnavailableError(BackendError):
    """Raised when a required external executable cannot be found."""


class BackendTimeoutError(BackendError):
    """Raised when an external backend exceeds its execution timeout."""


class BackendExecutionError(BackendError):
    """Raised when an external backend exits unsuccessfully."""

    def __init__(
        self,
        *,
        executable: str,
        returncode: int,
        stdout: str,
        stderr: str,
    ) -> None:
        super().__init__(f"backend {executable!r} exited with status {returncode}")
        self.executable = executable
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@dataclass(frozen=True, slots=True)
class BackendSpec:
    """Configuration describing one optional external executable."""

    name: str
    executable: str
    version_args: tuple[str, ...] = ("--version",)

    def __post_init__(self) -> None:
        name = self.name.strip()
        executable = self.executable.strip()

        if not name:
            raise ValueError("backend name must not be empty")

        if not executable:
            raise ValueError("backend executable must not be empty")

        object.__setattr__(self, "name", name)
        object.__setattr__(self, "executable", executable)


@dataclass(frozen=True, slots=True)
class BackendStatus:
    """Observed availability and version information for one backend."""

    name: str
    available: bool
    executable: Path | None = None
    version: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class BackendResult:
    """Captured result from a successful external backend invocation."""

    executable: Path
    arguments: tuple[str, ...]
    stdout: str
    stderr: str
    returncode: int


def discover_backend(spec: BackendSpec) -> BackendStatus:
    """Locate a configured backend executable on PATH."""

    resolved = shutil.which(spec.executable)

    if resolved is None:
        return BackendStatus(
            name=spec.name,
            available=False,
            error=f"executable {spec.executable!r} was not found on PATH",
        )

    return BackendStatus(
        name=spec.name,
        available=True,
        executable=Path(resolved),
    )


def run_backend(
    spec: BackendSpec,
    arguments: Sequence[str] = (),
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> BackendResult:
    """Run an external backend without invoking a command shell."""

    if timeout <= 0:
        raise ValueError("timeout must be greater than zero")

    status = discover_backend(spec)

    if not status.available or status.executable is None:
        raise BackendUnavailableError(
            status.error or f"backend {spec.name!r} is unavailable"
        )

    args = tuple(str(argument) for argument in arguments)

    try:
        completed = subprocess.run(
            [str(status.executable), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise BackendTimeoutError(
            f"backend {spec.name!r} exceeded timeout of {timeout} seconds"
        ) from exc

    if completed.returncode != 0:
        raise BackendExecutionError(
            executable=str(status.executable),
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    return BackendResult(
        executable=status.executable,
        arguments=args,
        stdout=completed.stdout,
        stderr=completed.stderr,
        returncode=completed.returncode,
    )


def probe_backend(
    spec: BackendSpec,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> BackendStatus:
    """Discover a backend and attempt to obtain its version string."""

    status = discover_backend(spec)

    if not status.available or status.executable is None:
        return status

    try:
        result = run_backend(
            spec,
            spec.version_args,
            timeout=timeout,
        )
    except BackendError as exc:
        return BackendStatus(
            name=spec.name,
            available=True,
            executable=status.executable,
            error=str(exc),
        )

    version = result.stdout.strip() or result.stderr.strip() or None

    return BackendStatus(
        name=spec.name,
        available=True,
        executable=status.executable,
        version=version,
    )


class BackendRegistry:
    """Collection of known optional external backends."""

    def __init__(self) -> None:
        self._specs: dict[str, BackendSpec] = {}

    def register(self, spec: BackendSpec) -> None:
        """Register one backend specification by stable name."""

        if spec.name in self._specs:
            raise ValueError(f"backend {spec.name!r} is already registered")

        self._specs[spec.name] = spec

    def get(self, name: str) -> BackendSpec:
        """Return a registered backend specification."""

        try:
            return self._specs[name]
        except KeyError as exc:
            raise KeyError(f"unknown backend {name!r}") from exc

    def names(self) -> tuple[str, ...]:
        """Return registered backend names in deterministic order."""

        return tuple(sorted(self._specs))

    def discover_all(self) -> dict[str, BackendStatus]:
        """Discover availability for every registered backend."""

        return {name: discover_backend(self._specs[name]) for name in self.names()}

    def probe_all(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> dict[str, BackendStatus]:
        """Probe availability and version information for every backend."""

        return {
            name: probe_backend(
                self._specs[name],
                timeout=timeout,
            )
            for name in self.names()
        }
