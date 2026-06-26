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
    window = PlotWindow(_StubDriver(), sink, [DRYBULB])

    sink.emit(_sample(is_warmup=True, value=5.0))  # warmup -> excluded
    sink.emit(_sample(is_warmup=False, value=9.0))
    window._refresh()

    _, y = window._curves[DRYBULB].getData()
    assert list(y) == [9.0]
