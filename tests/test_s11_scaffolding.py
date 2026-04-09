"""Tests for project scaffolding — pyproject.toml, package importability, version."""

from pathlib import Path

import tomllib


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_pyproject_exists():
    """pyproject.toml exists at the project root and is valid TOML."""
    pyproject = PROJECT_ROOT / "pyproject.toml"
    assert pyproject.is_file(), "pyproject.toml not found"
    with open(pyproject, "rb") as fh:
        data = tomllib.load(fh)
    assert "project" in data
    assert data["project"]["name"] == "oar"


def test_package_importable():
    """The ``oar`` package can be imported."""
    import oar  # noqa: F401 — just checking it resolves


def test_version_defined():
    """``oar.__version__`` is '0.1.0'."""
    import oar

    assert oar.__version__ == "0.1.0"
