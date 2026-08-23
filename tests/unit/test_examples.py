from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

EXAMPLES = Path(__file__).parents[2] / "examples"


def load_example(name: str) -> ModuleType:
    path = EXAMPLES / name
    spec = importlib.util.spec_from_file_location(
        f"example_{path.stem}",
        path,
    )

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_identification_example_imports() -> None:
    module = load_example("identify_release.py")

    assert callable(module.identify_path)
    assert callable(module.main)


def test_runtime_capability_example_imports() -> None:
    module = load_example("runtime_capabilities.py")

    assert callable(module.main)


def test_documented_example_files_exist() -> None:
    assert (EXAMPLES / "identify_release.py").is_file()
    assert (EXAMPLES / "runtime_capabilities.py").is_file()


def test_getting_started_references_executable_examples() -> None:
    root = Path(__file__).parents[2]
    guide = (root / "docs" / "getting-started.md").read_text()

    assert "examples/identify_release.py" in guide
    assert "examples/runtime_capabilities.py" in guide
    assert "build_default_detector" in guide
    assert "build_default_normalizer" in guide
    assert "PlaymatchResolver" in guide


def test_readme_links_getting_started() -> None:
    root = Path(__file__).parents[2]
    readme = (root / "README.md").read_text()

    assert "docs/getting-started.md" in readme
    assert "examples/" in readme
