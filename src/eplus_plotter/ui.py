"""pyqtgraph live-plot window — the v1 sink for the driver's Sample stream.

The swappable side of the SampleSink seam: it consumes Samples and knows nothing about
EnergyPlus. A QTimer drains the queue on the Qt thread so the worker thread never touches
widgets. Per-variable axis/visibility state lives in a Qt-free :class:`PlotModel`; this window
just mirrors it onto pyqtgraph curves and a control panel.
"""

from __future__ import annotations

import queue
from datetime import datetime, timedelta

import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets

from .driver import EnergyPlusDriver
from .plot_model import Axis, PlotModel
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
        self._model = PlotModel()
        self._curves: dict[VariableSpec, pg.PlotDataItem] = {}

        self.setWindowTitle("EnergyPlus Online Plotter")
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        outer = QtWidgets.QVBoxLayout(central)
        body = QtWidgets.QHBoxLayout()
        outer.addLayout(body, 1)

        # plot with independent left/right Y axes (separate ViewBoxes share the X axis)
        self._plot = pg.PlotWidget(axisItems={"bottom": pg.DateAxisItem()})
        self._pi = self._plot.getPlotItem()
        self._left_vb = self._pi.vb
        self._legend = self._pi.addLegend()
        self._pi.showGrid(x=True, y=True, alpha=0.3)
        self._pi.setLabel("left", "value (left axis)")
        self._right_vb = pg.ViewBox()
        self._pi.showAxis("right")
        self._pi.scene().addItem(self._right_vb)
        self._pi.getAxis("right").linkToView(self._right_vb)
        self._right_vb.setXLink(self._pi)
        self._pi.getAxis("right").setLabel("value (right axis)")
        self._left_vb.sigResized.connect(self._sync_right_geometry)
        body.addWidget(self._plot, 1)

        # per-variable control panel
        panel = QtWidgets.QScrollArea()
        panel.setWidgetResizable(True)
        panel.setFixedWidth(300)
        holder = QtWidgets.QWidget()
        self._controls = QtWidgets.QVBoxLayout(holder)
        self._controls.addWidget(QtWidgets.QLabel("Variables  (show · L/R axis)"))
        self._controls.addStretch(1)
        panel.setWidget(holder)
        body.addWidget(panel)

        # transport bar
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
        outer.addLayout(bar)

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(50)  # ~20 Hz

    def _sync_right_geometry(self) -> None:
        self._right_vb.setGeometry(self._left_vb.sceneBoundingRect())
        self._right_vb.linkedViewChanged(self._left_vb, self._right_vb.XAxis)

    # -- per-variable curves + controls (created lazily as specs appear) -----------------

    def _ensure_series(self, spec: VariableSpec) -> None:
        if spec in self._curves:
            return
        self._model.ensure(spec)
        curve = pg.PlotDataItem([], [], pen=pg.intColor(len(self._curves)), name=str(spec))
        self._curves[spec] = curve
        self._left_vb.addItem(curve)
        self._legend.addItem(curve, str(spec))
        self._add_control_row(spec)

    def _add_control_row(self, spec: VariableSpec) -> None:
        row = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        visible = QtWidgets.QCheckBox()
        visible.setChecked(True)
        visible.toggled.connect(lambda on, s=spec: self.set_visible(s, on))
        axis = QtWidgets.QComboBox()
        axis.addItems(["L", "R"])
        axis.currentTextChanged.connect(
            lambda text, s=spec: self.set_axis(s, Axis.RIGHT if text == "R" else Axis.LEFT)
        )
        label = QtWidgets.QLabel(str(spec))
        label.setWordWrap(True)
        layout.addWidget(visible)
        layout.addWidget(axis)
        layout.addWidget(label, 1)
        self._controls.insertWidget(self._controls.count() - 1, row)  # before the trailing stretch

    # -- view actions (wired to the controls; also exercised directly by tests) ----------

    def set_axis(self, spec: VariableSpec, axis: Axis) -> None:
        self._model.set_axis(spec, axis)
        curve = self._curves[spec]
        for vb in (self._left_vb, self._right_vb):
            if curve in vb.addedItems:
                vb.removeItem(curve)
        (self._right_vb if axis == Axis.RIGHT else self._left_vb).addItem(curve)

    def set_visible(self, spec: VariableSpec, visible: bool) -> None:
        self._model.set_visible(spec, visible)
        self._curves[spec].setVisible(visible)

    # -- transport ----------------------------------------------------------------------

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

    # -- streaming ----------------------------------------------------------------------

    def _refresh(self) -> None:
        # warmup days repeat the first design day; exclude them from the plot.
        touched: set[VariableSpec] = set()
        for s in drop_warmup(self._sink.drain()):
            ts = _sample_timestamp(s)
            for spec, value in s.values.items():
                self._ensure_series(spec)
                self._model.add_point(spec, ts, value)
                touched.add(spec)
        for spec in touched:
            series = self._model.series_for(spec)
            self._curves[spec].setData(series.x, series.y)
        if not self._driver.is_running and self._status.text() == "running":
            self._status.setText("error" if self._driver.error else "finished")
