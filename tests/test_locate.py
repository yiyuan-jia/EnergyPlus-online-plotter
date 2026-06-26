from pathlib import Path

import pytest

from eplus_plotter.locate import newest_install, parse_version


def test_parse_version():
    assert parse_version(Path(r"C:\EnergyPlusV25-2-0")) == (25, 2, 0)


def test_newest_install_picks_highest_numeric_version():
    # A lexicographic sort would wrongly rank V9-6-0 above V25-2-0 ('9' > '2').
    roots = [
        Path(r"C:\EnergyPlusV9-6-0"),
        Path(r"C:\EnergyPlusV24-2-0"),
        Path(r"C:\EnergyPlusV25-2-0"),
    ]
    assert newest_install(roots) == Path(r"C:\EnergyPlusV25-2-0")


def test_newest_install_empty_raises():
    with pytest.raises(FileNotFoundError):
        newest_install([])
