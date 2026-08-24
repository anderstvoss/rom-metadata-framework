from __future__ import annotations

import io
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from rom_metadata_framework import cli


def test_progress_reporter_non_tty_uses_stderr_lines() -> None:
    stream = io.StringIO()
    reporter = cli._ProgressReporter(
        verbose=False,
        stream=stream,
    )

    reporter.stage("Hashing physical file")
    reporter.stage("Looking up physical file")
    reporter.finish("Identified")

    assert stream.getvalue().splitlines() == [
        "[progress] Hashing physical file",
        "[progress] Looking up physical file",
        "✓ Identified",
    ]


def test_verbose_reporter_uses_timed_multiline_output() -> None:
    stream = io.StringIO()
    reporter = cli._ProgressReporter(
        verbose=True,
        stream=stream,
    )

    reporter.stage("Hashing physical file")
    reporter.stage("Inspecting structure")
    reporter.finish("Local identification")

    lines = stream.getvalue().splitlines()

    assert len(lines) == 3
    assert lines[0].endswith(
        "] Hashing physical file"
    )
    assert lines[1].endswith(
        "] Inspecting structure"
    )
    assert lines[2].startswith(
        "✓ Local identification ("
    )
    assert lines[2].endswith("s)")


def test_progress_and_verbose_are_mutually_exclusive() -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(
            [
                "identify",
                "sample.bin",
                "--progress",
                "--verbose",
            ]
        )

    assert exc.value.code == 2


@pytest.mark.parametrize(
    "command",
    (
        "identify",
        "plan-rename",
        "rename",
        "verify",
    ),
)
def test_identification_commands_expose_progress_flags(
    command: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main([command, "--help"])

    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert "--progress" in output
    assert "--verbose" in output


@pytest.mark.parametrize(
    "progress_flag",
    (
        "--progress",
        "--verbose",
    ),
)
def test_json_output_remains_stdout_only_with_progress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    progress_flag: str,
) -> None:
    path = tmp_path / "sample.bin"
    path.write_bytes(b"x")

    result = SimpleNamespace(
        canonical_match=None,
        local_metadata=None,
        platform_detection=SimpleNamespace(
            best=None,
        ),
        physical_representation=None,
        physical_identity=SimpleNamespace(
            hashes=None,
        ),
        normalized_content=None,
        requested_identity=None,
        provider_name="playmatch",
        physical_lookup=None,
        normalized_lookup=None,
        identification_strength="local_strong",
        title_source=None,
        display_title=None,
        provider_unavailable=False,
        has_release_conflict=False,
        has_platform_conflict=False,
        identified=False,
    )

    def fake_identify_file(*args, **kwargs):
        progress = kwargs["progress"]
        progress("Hashing physical file")
        progress("Reconciling evidence")
        return result

    monkeypatch.setattr(
        cli,
        "identify_file",
        fake_identify_file,
    )

    rc = cli.main(
        [
            "identify",
            str(path),
            "--json",
            progress_flag,
        ]
    )

    assert rc == 0

    captured = capsys.readouterr()
    assert captured.out.startswith("{")
    assert "[progress]" not in captured.out
    if progress_flag == "--progress":
        assert (
            "[progress] Hashing physical file"
            in captured.err
        )
    else:
        assert "] Hashing physical file" in captured.err

    assert "✓ Local identification" in captured.err


def test_progress_result_prioritizes_identification_conflict() -> None:
    result = SimpleNamespace(
        identification_strength="catalogue",
        provider_unavailable=False,
        has_release_conflict=True,
        has_platform_conflict=False,
    )

    assert cli._identification_progress_result(
        result
    ) == (
        "✗",
        "Identification conflict",
    )


class _TTYStringIO(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_progress_reporter_tty_animates_and_clears() -> None:
    stream = _TTYStringIO()
    reporter = cli._ProgressReporter(
        verbose=False,
        stream=stream,
        interval=0.01,
    )

    reporter.stage("Hashing physical file")
    time.sleep(0.03)
    reporter.finish("Identified")

    output = stream.getvalue()

    assert "\r" in output
    assert "Hashing physical file" in output
    assert "\033[K" in output
    assert output.endswith("✓ Identified\n")


def test_progress_reporter_cancel_stops_tty_animation() -> None:
    stream = _TTYStringIO()
    reporter = cli._ProgressReporter(
        verbose=False,
        stream=stream,
        interval=0.01,
    )

    reporter.stage("Hashing physical file")
    time.sleep(0.02)
    reporter.cancel()

    thread = reporter._thread

    assert thread is None
    assert "\033[K" in stream.getvalue()


def test_unexpected_identification_exception_cleans_progress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "sample.bin"
    path.write_bytes(b"x")

    cancelled = False

    class Reporter:
        def __init__(self, **kwargs) -> None:
            pass

        def stage(self, stage: str) -> None:
            pass

        def cancel(self) -> None:
            nonlocal cancelled
            cancelled = True

        def finish(
            self,
            message: str,
            *,
            symbol: str = "✓",
        ) -> None:
            raise AssertionError(
                "unexpected exception must cancel, not finish"
            )

    def fail_identification(*args, **kwargs):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(
        cli,
        "_ProgressReporter",
        Reporter,
    )
    monkeypatch.setattr(
        cli,
        "identify_file",
        fail_identification,
    )

    with pytest.raises(
        RuntimeError,
        match="unexpected",
    ):
        cli._run_identification_workflow(
            path,
            as_json=False,
            normalize=True,
            conflict_context="test",
            progress_mode="progress",
        )

    assert cancelled
