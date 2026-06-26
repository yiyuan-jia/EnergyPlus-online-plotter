"""The plot's view-model: per-variable data buffers, axis assignment, and visibility.

Kept free of Qt so the assignment/visibility logic is unit-testable. The Qt window mirrors
this state onto pyqtgraph curves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .sample import VariableSpec


class Axis(Enum):
    LEFT = "left"
    RIGHT = "right"


@dataclass
class Series:
    spec: VariableSpec
    x: list[float] = field(default_factory=list)
    y: list[float] = field(default_factory=list)
    axis: Axis = Axis.LEFT
    visible: bool = True


class PlotModel:
    def __init__(self) -> None:
        self._series: dict[VariableSpec, Series] = {}

    def ensure(self, spec: VariableSpec) -> Series:
        series = self._series.get(spec)
        if series is None:
            series = Series(spec)
            self._series[spec] = series
        return series

    def add_point(self, spec: VariableSpec, x: float, y: float) -> None:
        series = self.ensure(spec)
        series.x.append(x)
        series.y.append(y)

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
