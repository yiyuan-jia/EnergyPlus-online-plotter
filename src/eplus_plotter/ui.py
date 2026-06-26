"""pyqtgraph live-plot window — the v1 sink for the driver's Sample stream.

This is the swappable side of the SampleSink seam: it consumes Samples and knows nothing about
EnergyPlus. A QTimer drains the queue on the Qt thread so the driver's worker thread never
touches widgets.
"""

from __future__ import annotations

import queue
from datetime import datetime, timedelta

import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets

from .driver import EnergyPlusDriver
from .sample import Sample, VariableSpec, drop_warmup

# EnergyPlus reports day-of-year + hour-of-day; anchor to a nominal non-leap year for the axis.
_EPOCH = datetime(2001, 1, 1)


def _sample_timestamp(s: Sample) -> float:
    return (_EPOCH + timedelta(days=s.day_of_year - 1, hours=s.current_time)).timestamp()


class QueueSink:
    """A SampleSink that hands Samples to the UI thread through a thread-safe queue."""

    def __init__(self) -> None:
        self._q: "queue.Queue[Sample]" = queue.Queue()

    def emit(self, sample: Sample) -> None:
        self._q.put(sample)

    def drain(self) -> list[Sample]:
        out: list[Sample] = []
        try:
            while True:
                out.append(self._q.get_nowait())
        except queue.Empty:
            pass
        return out


class PlotWindow(QtWidgets.QMainWindow):
    def __init__(self, driver: EnergyPlusDriver, sink: QueueSink) -> None:
        super().__init__()
        self._driver = driver
        self._sink = sink
        self._paused = False

        self.setWindowTitle("EnergyPlus Online Plotter")
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        self._plot = pg.PlotWidget(axisItems={"bottom": pg.DateAxisItem()})
        self._plot.addLegend()
        self._plot.setLabel("left", "value")
        self._plot.showGrid(x=True, y=True, alpha=0.3)
        layout.addWidget(self._plot)

        # Curves are created lazily as variables appear in the stream (e.g. after '*' expansion).
        self._x: dict[VariableSpec, list[float]] = {}
        self._y: dict[VariableSpec, list[float]] = {}
        self._curves: dict[VariableSpec, pg.PlotDataItem] = {}

        bar = QtWidgets.QHBoxLayout()
        self._pause_btn = QtWidgets.QPushButton("Pause")
        self._abort_btn = QtWidgets.QPushButton("Abort")
        self._pause_btn.clicked.connect(self._toggle_pause)
        self._abort_btn.clicked.connect(self._on_abort)
        self._status = QtWidgets.QLabel("running")
        bar.addWidget(self._pause_btn)
        bar.addWidget(self._abort_btn)
        bar.addStretch(1)
        bar.addWidget(self._status)
        layout.addLayout(bar)

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(50)  # ~20 Hz

    def _toggle_pause(self) -> None:
        if self._paused:
            self._driver.resume()
            self._paused = False
            self._pause_btn.setText("Pause")
            self._status.setText("running")
        else:
            self._driver.pause()
            self._paused = True
            self._pause_btn.setText("Resume")
            self._status.setText("paused")

    def _on_abort(self) -> None:
        self._driver.abort()
        self._status.setText("aborted")
        self._pause_btn.setEnabled(False)
        self._abort_btn.setEnabled(False)

    def _ensure_curve(self, spec: VariableSpec) -> None:
        if spec not in self._curves:
            self._x[spec] = []
            self._y[spec] = []
            self._curves[spec] = self._plot.plot(
                [], [], pen=pg.intColor(len(self._curves)), name=str(spec)
            )

    def _refresh(self) -> None:
        # warmup days repeat the first design day; exclude them from the plot.
        touched: set[VariableSpec] = set()
        for s in drop_warmup(self._sink.drain()):
            ts = _sample_timestamp(s)
            for spec, value in s.values.items():
                self._ensure_curve(spec)
                self._x[spec].append(ts)
                self._y[spec].append(value)
                touched.add(spec)
        # Repaint each affected curve once per tick, not once per sample.
        for spec in touched:
            self._curves[spec].setData(self._x[spec], self._y[spec])
        if not self._driver.is_running and self._status.text() == "running":
            self._status.setText("error" if self._driver.error else "finished")
