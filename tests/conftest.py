import os
import threading

import pytest

# Run Qt without a display so the UI smoke test works headless / in CI.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from eplus_plotter.locate import locate_energyplus
from eplus_plotter.sample import Sample


@pytest.fixture(scope="session")
def eplus_root():
    try:
        return locate_energyplus()
    except FileNotFoundError:
        pytest.skip("no EnergyPlus install found")


@pytest.fixture
def eplus_model(eplus_root):
    """(root, idf, epw) for a small bundled single-zone model."""
    idf = eplus_root / "ExampleFiles" / "1ZoneUncontrolled.idf"
    epw = eplus_root / "WeatherData" / "USA_CA_San.Francisco.Intl.AP.724940_TMY3.epw"
    if not idf.exists() or not epw.exists():
        pytest.skip("bundled example files not found")
    return eplus_root, idf, epw


class RecordingSink:
    """A SampleSink that just collects everything it's given (thread-safe)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._samples: list[Sample] = []

    def emit(self, sample: Sample) -> None:
        with self._lock:
            self._samples.append(sample)

    def count(self) -> int:
        with self._lock:
            return len(self._samples)

    def snapshot(self) -> list[Sample]:
        with self._lock:
            return list(self._samples)


@pytest.fixture
def recording_sink() -> RecordingSink:
    return RecordingSink()
