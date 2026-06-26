"""The value types crossing the host-to-UI seam.

The EnergyPlus driver emits :class:`Sample` objects to a :class:`SampleSink`. Nothing here
imports EnergyPlus or any UI toolkit, so both sides of the seam stay decoupled.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol, runtime_checkable


@dataclass(frozen=True)
class VariableSpec:
    """An EnergyPlus output variable, identified by ``(name, key)``."""

    name: str
    key: str

    def __str__(self) -> str:
        return f"{self.name} [{self.key}]"


@dataclass
class Sample:
    """One reading of every tracked variable at a single simulation timestep."""

    day_of_year: int
    current_time: float  # fractional hour within the day (e.g. 13.25 == 13:15)
    sim_time_hours: float  # cumulative simulated hours since the run started
    is_warmup: bool
    values: dict[VariableSpec, float]


@runtime_checkable
class SampleSink(Protocol):
    """Anything the driver can hand Samples to — a UI queue now, a websocket later."""

    def emit(self, sample: Sample) -> None: ...


def drop_warmup(samples: Iterable[Sample]) -> list[Sample]:
    """Warmup days repeat the first design day and are excluded from plots."""
    return [s for s in samples if not s.is_warmup]
