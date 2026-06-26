import time

import pytest

from eplus_plotter.driver import EnergyPlusDriver
from eplus_plotter.sample import VariableSpec

DRYBULB = VariableSpec("Site Outdoor Air Drybulb Temperature", "Environment")


def _wait_until(pred, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if pred():
            return True
        time.sleep(0.02)
    return pred()


@pytest.mark.eplus
def test_driver_streams_pauses_resumes_aborts(eplus_model, recording_sink, tmp_path):
    """The whole driver spine through the SampleSink seam, in one real run.

    Combined into a single run because each EnergyPlus run is expensive; it exercises the
    four behaviors of #2/#6/#7 in sequence.
    """
    root, idf, epw = eplus_model
    driver = EnergyPlusDriver(
        root, idf, epw, tmp_path, [DRYBULB], recording_sink, throttle=0.01
    )
    driver.start()
    try:
        # STREAM: real values arrive across the seam
        assert _wait_until(lambda: recording_sink.count() >= 10, 60), "no samples streamed"
        sample = recording_sink.snapshot()[5]
        assert DRYBULB in sample.values
        assert -90.0 < sample.values[DRYBULB] < 90.0
        assert sample.sim_time_hours >= 0.0
        # warmup samples must never reach the sink (#8)
        assert all(not s.is_warmup for s in recording_sink.snapshot())

        # PAUSE: blocking the callback stalls the stream
        driver.pause()
        time.sleep(0.3)  # let any in-flight callback settle
        paused_at = recording_sink.count()
        time.sleep(0.8)
        assert recording_sink.count() == paused_at, "stream did not stall while paused"

        # RESUME: the stream continues
        driver.resume()
        assert _wait_until(lambda: recording_sink.count() > paused_at, 60), "did not resume"

        # ABORT: stop_simulation ends the run promptly (well before a full annual run)
        driver.abort()
        driver.join(timeout=30)
        assert not driver.is_running, "run did not stop after abort"
    finally:
        driver.abort()
        driver.join(timeout=30)


@pytest.mark.eplus
def test_annual_flag_excludes_design_days(eplus_model, recording_sink, tmp_path):
    """EnergyPlus --annual skips the sizing design days, so the stream starts at the run period."""
    root, idf, epw = eplus_model
    driver = EnergyPlusDriver(
        root, idf, epw, tmp_path, [DRYBULB], recording_sink,
        extra_args=["--annual"], throttle=0.0,
    )
    driver.start()
    driver.join(timeout=180)
    samples = recording_sink.snapshot()
    assert samples
    assert samples[0].day_of_year == 1  # run period starts Jan 1, no Dec-21/Jul-21 design days


@pytest.mark.eplus
def test_star_key_expands_to_one_series_per_key(eplus_model, recording_sink, tmp_path):
    """A '*' key resolves to one concrete (name, key) series per matching component."""
    root, idf, epw = eplus_model
    specs = [VariableSpec("Surface Inside Face Temperature", "*")]  # declared in the model
    driver = EnergyPlusDriver(root, idf, epw, tmp_path, specs, recording_sink, throttle=0.005)
    driver.start()
    try:
        assert _wait_until(lambda: recording_sink.count() >= 3, 60), "no samples streamed"
        sample = recording_sink.snapshot()[-1]
        names = {spec.name for spec in sample.values}
        keys = {spec.key for spec in sample.values}
        assert names == {"Surface Inside Face Temperature"}
        assert "*" not in keys  # the wildcard was expanded
        assert len(keys) >= 2  # one series per surface
    finally:
        driver.abort()
        driver.join(timeout=30)
