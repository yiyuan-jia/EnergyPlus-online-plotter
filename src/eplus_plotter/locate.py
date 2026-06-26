"""Find an EnergyPlus install and load its pyenergyplus Runtime API.

EnergyPlus installs live at ``C:\\EnergyPlusV<major>-<minor>-<patch>``. The install must be
selected by **numeric** version: a lexicographic sort ranks ``V9-6-0`` above ``V25-2-0``
(``'9' > '2'``) and would silently load an ancient build whose API lacks ``stop_simulation``.
"""

from __future__ import annotations

import glob
import os
import sys
from pathlib import Path
from typing import Iterable

DEFAULT_GLOB = r"C:\EnergyPlusV*"


def parse_version(path: Path | str) -> tuple[int, ...]:
    """``...EnergyPlusV25-2-0`` -> ``(25, 2, 0)``."""
    name = Path(path).name.replace("EnergyPlusV", "")
    return tuple(int(chunk) if chunk.isdigit() else 0 for chunk in name.split("-"))


def newest_install(roots: Iterable[Path]) -> Path:
    """The install with the highest numeric version. Raises if ``roots`` is empty."""
    roots = list(roots)
    if not roots:
        raise FileNotFoundError("no EnergyPlus installs provided")
    return max(roots, key=parse_version)


def find_installs(pattern: str = DEFAULT_GLOB) -> list[Path]:
    """All installs under ``pattern`` that actually contain a ``pyenergyplus`` package."""
    return [Path(p) for p in glob.glob(pattern) if (Path(p) / "pyenergyplus").is_dir()]


def locate_energyplus(root: Path | str | None = None) -> Path:
    """Resolve the EnergyPlus install root.

    With ``root`` given, validate and return it. Otherwise pick the newest install found.
    """
    if root is not None:
        root = Path(root)
        if not (root / "pyenergyplus").is_dir():
            raise FileNotFoundError(f"no pyenergyplus package under {root}")
        return root
    installs = find_installs()
    if not installs:
        raise FileNotFoundError(f"no EnergyPlus install found under {DEFAULT_GLOB}")
    return newest_install(installs)


def load_api(root: Path | str):
    """Wire ``sys.path`` + the DLL search dir for this install and return a fresh API.

    Returns an ``EnergyPlusAPI`` instance. Importing this module does not import
    ``pyenergyplus``; that only happens here, so the rest of the package (and most tests)
    stay free of the native dependency.
    """
    root = Path(root)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    os.add_dll_directory(str(root))  # so energyplusapi.dll resolves
    from pyenergyplus.api import EnergyPlusAPI

    return EnergyPlusAPI()
