"""Named-vault registry — persist named vault locations at ``~/.config/oar/vaults.yaml``.

The registry maps human-friendly names to absolute vault paths and records an
optional default. Location respects ``XDG_CONFIG_HOME`` so it is fully testable.

On-disk shape::

    vaults:
      work: /Users/me/work-vault
      personal: /Users/me/notes
    default: work
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml


def config_dir() -> Path:
    """Return the OAR config directory, honoring ``XDG_CONFIG_HOME``."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "oar"


def registry_path() -> Path:
    """Return the absolute path to ``vaults.yaml``."""
    return config_dir() / "vaults.yaml"


def load() -> dict:
    """Load the registry. Returns an empty registry when missing or malformed."""
    path = registry_path()
    if not path.exists():
        return {"vaults": {}, "default": None}
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except (yaml.YAMLError, OSError):
        return {"vaults": {}, "default": None}
    vaults = data.get("vaults") or {}
    if not isinstance(vaults, dict):
        vaults = {}
    default = data.get("default")
    if default not in vaults:
        default = None
    return {"vaults": {str(k): str(v) for k, v in vaults.items()}, "default": default}


def save(data: dict) -> None:
    """Persist *data* to ``vaults.yaml`` (creating parent dirs as needed)."""
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "vaults": dict(data.get("vaults", {})),
        "default": data.get("default"),
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=True, default_flow_style=False))


def add(name: str, path: str | Path) -> dict:
    """Register *name* → absolute path. Auto-sets default when none exists yet."""
    data = load()
    abs_path = str(Path(path).expanduser().resolve())
    had_default = data.get("default") is not None
    data["vaults"][name] = abs_path
    if not had_default:
        # First named vault becomes the default for convenience.
        data["default"] = name
    save(data)
    return data


def remove(name: str) -> dict:
    """Remove *name* from the registry. Clears default if it pointed at *name*."""
    data = load()
    data["vaults"].pop(name, None)
    if data.get("default") == name:
        data["default"] = None
    save(data)
    return data


def set_default(name: str) -> dict:
    """Set the default vault to *name*. Raises ``KeyError`` if unknown."""
    data = load()
    if name not in data["vaults"]:
        raise KeyError(name)
    data["default"] = name
    save(data)
    return data


def resolve_name(name: str) -> Path | None:
    """Resolve a registry *name* to its path, or ``None`` when not registered."""
    data = load()
    p = data["vaults"].get(name)
    return Path(p) if p else None


def default_name() -> str | None:
    """Return the name of the default vault, or ``None``."""
    return load().get("default")
