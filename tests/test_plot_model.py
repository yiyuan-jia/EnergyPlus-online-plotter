from eplus_plotter.plot_model import Axis, PlotModel
from eplus_plotter.sample import VariableSpec

A = VariableSpec("Zone Mean Air Temperature", "ZONE ONE")
B = VariableSpec("Surface Inside Face Temperature", "WALL")


def test_new_series_defaults_to_left_axis_and_visible():
    m = PlotModel()
    m.add_point(A, 1.0, 20.0)
    s = m.series_for(A)
    assert s.axis == Axis.LEFT
    assert s.visible is True
    x, y = s.buf.xy()
    assert list(x) == [1.0] and list(y) == [20.0]


def test_add_point_appends():
    m = PlotModel()
    m.add_point(A, 1.0, 20.0)
    m.add_point(A, 2.0, 21.0)
    x, y = m.series_for(A).buf.xy()
    assert list(x) == [1.0, 2.0]
    assert list(y) == [20.0, 21.0]


def test_set_axis_and_visibility():
    m = PlotModel()
    m.add_point(A, 1.0, 20.0)
    m.set_axis(A, Axis.RIGHT)
    m.set_visible(A, False)
    s = m.series_for(A)
    assert s.axis == Axis.RIGHT
    assert s.visible is False


def test_all_series_in_insertion_order():
    m = PlotModel()
    m.add_point(B, 1.0, 5.0)
    m.add_point(A, 1.0, 20.0)
    assert [s.spec for s in m.all_series()] == [B, A]
