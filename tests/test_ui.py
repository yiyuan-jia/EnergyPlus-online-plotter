import pytest

from eplus_plotter.sample import Sample, VariableSpec

DRYBULB = VariableSpec("Site Outdoor Air Drybulb Temperature", "Environment")


class _StubDriver:
    is_running = True
    error = None

    def pause(self) -> None: ...
    def resume(self) -> None: ...
    def abort(self) -> None: ...


@pytest.fixture
def qapp():
    from pyqtgraph.Qt import QtWidgets

    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _sample(is_warmup: bool, value: float) -> Sample:
    return Sample(
        day_of_year=1,
        current_time=value,
        sim_time_hours=value,
        is_warmup=is_warmup,
        values={DRYBULB: value},
    )


def test_plot_window_drains_samples_and_excludes_warmup(qapp):
    from eplus_plotter.ui import PlotWindow, QueueSink

    sink = QueueSink()
    window = PlotWindow(_StubDriver(), sink)

    sink.emit(_sample(is_warmup=True, value=5.0))  # warmup -> excluded
    sink.emit(_sample(is_warmup=False, value=9.0))
    window._refresh()

    _, y = window._curves[DRYBULB].getData()
    assert list(y) == [9.0]


def test_axis_assignment_and_visibility(qapp):
    from eplus_plotter.plot_model import Axis
    from eplus_plotter.ui import PlotWindow, QueueSink

    sink = QueueSink()
    window = PlotWindow(_StubDriver(), sink)
    sink.emit(_sample(is_warmup=False, value=9.0))
    window._refresh()
    curve = window._curves[DRYBULB]

    # a new series starts on the left axis, visible
    assert curve in window._left_vb.addedItems
    assert curve.isVisible()

    # hide it
    window.set_visible(DRYBULB, False)
    assert not curve.isVisible()
    assert window._model.series_for(DRYBULB).visible is False

    # move it to the right axis (independent ViewBox)
    window.set_axis(DRYBULB, Axis.RIGHT)
    assert curve in window._right_vb.addedItems
    assert curve not in window._left_vb.addedItems
    assert window._model.series_for(DRYBULB).axis == Axis.RIGHT
