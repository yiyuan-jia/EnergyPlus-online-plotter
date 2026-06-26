from eplus_plotter.sample import Sample, VariableSpec, drop_warmup

DRYBULB = VariableSpec("Site Outdoor Air Drybulb Temperature", "Environment")


def _sample(is_warmup: bool) -> Sample:
    return Sample(
        day_of_year=1,
        current_time=1.0,
        sim_time_hours=1.0,
        is_warmup=is_warmup,
        values={DRYBULB: 10.0},
    )


def test_drop_warmup_removes_warmup_samples():
    samples = [_sample(True), _sample(False), _sample(True), _sample(False)]
    kept = drop_warmup(samples)
    assert len(kept) == 2
    assert all(not s.is_warmup for s in kept)
