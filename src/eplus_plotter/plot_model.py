"""The plot's view-model: per-variable data buffers, axis assignment, and visibility.

Kept free of Qt so the assignment/visibility logic is unit-testable. The Qt window mirrors
this state onto pyqtgraph curves. Each series is backed by a fixed-capacity ring buffer so
memory stays bounded over a long run.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .ring_buffer import RingBuffer
from .sample import VariableSpec

# Covers a 4-6 timestep/hour annual run (35k-52k points) without rolling; ~1 MB/series.
DEFAULT_CAPACITY = 60_000


class Axis(Enum):
    LEFT = "left"
    RIGHT = "right"


@dataclass
class Series:
    spec: VariableSpec
    buf: RingBuffer
    axis: Axis = Axis.LEFT
    visible: bool = True


class PlotModel:
    def __init__(self, capacity: int = DEFAULT_CAPACITY) -> None:
        self._capacity = capacity
        self._series: dict[VariableSpec, Series] = {}

    def ensure(self, spec: VariableSpec) -> Series:
        series = self._series.get(spec)
        if series is None:
            series = Series(spec, RingBuffer(self._capacity))
            self._series[spec] = series
        return series

    def add_point(self, spec: VariableSpec, x: float, y: float) -> None:
        self.ensure(spec).buf.append(x, y)

    def set_axis(self, spec: VariableSpec, axis: Axis) -> None:
        self.ensure(spec).axis = axis

    def set_visible(self, spec: VariableSpec, visible: bool) -> None:
        self.ensure(spec).visible = visible

    def series_for(self, spec: VariableSpec) -> Series:
        return self._series[spec]

    def all_series(self) -> list[Series]:
        return list(self._series.values())

    def __contains__(self, spec: VariableSpec) -> bool:
        return spec in self._series
