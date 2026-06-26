# Handoff — EnergyPlus Online Plotter

_Last updated: 2026-06-25. Read this to resume cold._

## TL;DR

**v1 is functionally complete and verified.** A `uv`-installable CLI drives EnergyPlus 25.2 via
the `pyenergyplus` Runtime API and **live-plots** a running simulation's declared
`Output:Variable`s in a pyqtgraph window — with pause/resume/abort, dual Y-axes, per-variable
show/hide, and bounded-memory downsampling. **20 tests pass, mypy clean.** All eight implementation
issues (#2–#9) are closed; only #1 (the PRD epic) stays open as the tracking umbrella.

## Run / dev (Windows, EnergyPlus 25.2 at `C:\EnergyPlusV25-2-0`)

```
uv sync --extra dev --extra ui
uv run eplus-plotter run <model.idf> -w <weather.epw> [-d out] [--var NAME ...] \
        [--throttle 0.02] [--include-sizing] [--eplus-root PATH]
uv run pytest                 # full suite ('eplus'-marked tests need an install)
uv run pytest tests/test_driver.py::test_annual_flag_excludes_design_days   # single
uv run mypy
```
Repo: `github.com/yiyuan-jia/EnergyPlus-online-plotter` (push as collaborator `yiyuan1840`).

## What works (issues, all CLOSED)

| # | Capability |
|---|---|
| 2 | Drive the run on a worker thread; stream a variable to a live pyqtgraph window (the spine) |
| 3 | Stream the model's declared `Output:Variable`s; `*` keys expanded to one series per component |
| 4 | Per-variable **left/right Y-axis** + **show/hide** controls |
| 5 | **Ring buffers + autoDownsample** — smooth, bounded-memory annual runs; "Reset view" button |
| 6 | **Pause/resume** (block the Sampler callback on a threading.Event) |
| 7 | **Abort** (`runtime.stop_simulation`), window stays interactive after |
| 8 | Skip **warmup** (no blank-plot delay, not throttled) |
| 9 | Skip **sizing design days** via EnergyPlus `--annual` (default on) |

## Architecture (src/eplus_plotter/)

- `locate.py` — find install by **numeric** version; wire `sys.path` + DLL dir; `load_api()`.
- `idf_outputs.py` — parse `Output:Variable` → `VariableSpec(name, key)`.
- `sample.py` — `Sample`, **`SampleSink` protocol (the seam)**, `drop_warmup`.
- `driver.py` — `EnergyPlusDriver`: worker thread runs `run_energyplus`; Sampler callback at
  `callback_end_zone_timestep_after_zone_reporting`; `*` expansion via `get_api_data`; skips
  warmup + non-weather environments; pause/resume/abort.
- `ring_buffer.py` — fixed-capacity numpy `(x, y)` buffer (bounds memory).
- `plot_model.py` — Qt-free `PlotModel`/`Series`/`Axis` (buffers, axis, visibility) — unit-tested.
- `ui.py` — pyqtgraph `PlotWindow`: dual ViewBoxes, control panel, transport bar, lazy curves.
- `cli.py` / `__main__.py` — `eplus-plotter run …`.

## Decisions / gotchas (don't re-derive — also ADRs 0001–0004 in `docs/prd/online-plotter.md`)

- **Driver mode** (own the run via the API), not plugin/file-tailing.
- **In-process thread + queue**; pause = block the callback, abort = `stop_simulation`. No subprocess.
- **SampleSink seam** keeps host/UI decoupled → the future web frontend swaps only the sink.
- **Target EnergyPlus 25.2.** `stop_simulation` is absent in old installs (V9.x).
- **Locate by numeric version** — a string sort ranks `V9-6-0` above `V25-2-0`.
- Declared `Output:Variable`s don't need `request_variable`; `*` keys can't be requested (rely on
  the declaration) and are expanded at runtime.
- `--annual` skips design days but **forces a full-year run** → use `--include-sizing` to keep a
  model's custom (sub-annual) RunPeriod. It does NOT break autosizing (sizing calcs still run).
- Ring buffer capacity default **60_000** (~annual at 4–6 timesteps/h). **`clipToView` was dropped**
  — it conflicts with moving curves between the dual-axis ViewBoxes; `autoDownsample(method="peak")`
  is the win (its band = the per-segment min/max envelope, so spikes aren't hidden).
- **Commits carry no Claude co-author trailer** (user preference).

## Verified (not just built)

- Streamed annual drybulb **== Denver EPW ground truth exactly** (min −25, max 36, mean 9.76 °C).
- `5ZoneAirCooled` / Chicago: **heating in winter, cooling in summer**, peaks 15.8 / 14.0 kW —
  physically correct; `*` expanded across all 5 zones.
- Dual-axis and 50k-point downsampling confirmed via headless PNG renders.

## Next session — pick up here

- **North star: web/shareable frontend.** Add a `WebSocketSink` (implements `SampleSink`) and a
  browser app (Plotly.js/ECharts); the engine is untouched. This is the highest-value next step.
- Backlog (not yet issues): plugin-mode adapter (plot runs launched from CBECC/EP-Launch);
  system-timestep (sub-zone-timestep) sampling for HVAC; multi-run overlay/compare; session
  save/export; configurable per-series ring-buffer capacity; friendlier errors (missing IDF/EPW).
- `#1` (PRD epic) is intentionally left open as the umbrella.

## Local-only (gitignored, not committed)

`prototypes/` (driver-spine prototype + `NOTES.md`) and the scratchpad render/verify scripts
(`verify_drybulb.py`, `render_dualaxis.py`, `render_big.py`, `render_hvac.py`, `probe_kind.py`).
