# PRD: EnergyPlus Online Plotter (v1)

_Uses the project glossary: **Online Plotter**, **Driver mode**, **Sample**, **Sampler
callback**, **Variable handle**, **(variable name, key)**, **Warmup**, **Zone timestep**,
**SampleSink**._

## Problem Statement

As an EnergyPlus modeler, I am blind while a simulation runs. EnergyPlus does not reliably flush
its output files mid-run, so I cannot tell whether a model is diverging, stuck, or producing
nonsense until the run finishes and I open `eplusout.csv`. For long annual runs that means
minutes-to-hours wasted before I discover a problem I could have spotted in the first few sim
days. TRNSYS has long had an "Online Plotter" that shows results live as the simulation advances;
EnergyPlus has no equivalent.

## Solution

A local **Online Plotter** that drives an EnergyPlus run and plots its declared `Output:Variable`
values live as the simulation advances. I point it at an IDF and an EPW; it streams each
variable at the **zone timestep**, lets me assign variables to a left or right Y-axis, zoom and
pan over elapsed sim time, show/hide individual variables, and **pause, resume, or abort** the
running simulation from the UI — so I can watch a run unfold and kill a bad one early instead of
waiting for it to finish.

v1 is a single local script run under an installed EnergyPlus's bundled Python. It is architected
behind a **SampleSink** seam so a future shareable/web frontend reuses the entire engine and only
the UI is replaced.

## Supported environment

- **EnergyPlus 25.2** (`C:\EnergyPlusV25-2-0`, bundled Python 3.13) is the supported target.
  Older installs that predate `runtime.stop_simulation` (e.g. V9.x) are out of scope.

## User Stories

1. As a modeler, I want to launch the plotter against my IDF and EPW from one command, so that I can start watching a run without extra setup.
2. As a modeler, I want the plotter to find my installed EnergyPlus 25.2 automatically, so that I don't have to configure paths by hand.
3. As a modeler, I want to override which EnergyPlus install is used, so that I can point at a specific copy.
4. As a modeler, I want the plotter to stream the variables my model already declares as `Output:Variable`, so that I see what I asked for without redefining it elsewhere.
5. As a modeler, I want `Output:Variable` entries with a `*` key expanded to one curve per matching key (e.g. per zone), so that I see every instance the model reports.
6. As a modeler, I want each variable drawn as a live line that advances as the simulation steps forward, so that I perceive the run's progress in real time.
7. As a modeler, I want the x-axis to show real simulation date/time, so that I can locate behavior at a specific point in the run period.
8. As a modeler, I want warmup timesteps excluded from the plotted series, so that repeated warmup days don't distort the picture.
9. As a modeler, I want to assign any variable to the left or right Y-axis, so that I can compare quantities with different units or magnitudes (e.g. temperature vs. load).
10. As a modeler, I want to show or hide individual variables while the run continues, so that I can focus on the ones I care about without restarting.
11. As a modeler, I want to zoom and pan over the elapsed sim time, so that I can inspect a spike or transition in detail.
12. As a modeler, I want to pause the running simulation from the UI, so that I can study the current state without it advancing.
13. As a modeler, I want to resume a paused simulation, so that I can continue after inspecting it.
14. As a modeler, I want to abort the running simulation from the UI, so that I can kill a diverging or wrong run immediately instead of waiting for it to finish.
15. As a modeler, after aborting, I want the plot window to stay interactive (zoom/pan still work), so that I can study what went wrong with the partial results.
16. As a modeler, I want the plotter to stay responsive during a full annual run, so that watching does not become slower than the simulation itself.
17. As a modeler, I want the streamed values to match what `eplusout.csv` reports for the same timesteps, so that I can trust what I see live.
18. As a modeler running a single-zone test model, I want it to work end-to-end out of the box, so that I can validate the tool quickly.
19. As a modeler, I want clear feedback if my IDF declares no `Output:Variable` objects, so that I understand why nothing is plotting.
20. As a modeler, I want the output directory configurable, so that EnergyPlus artifacts land where I expect.
21. As a future maintainer, I want the EnergyPlus host logic isolated from the plot UI behind a stable seam, so that I can add a web frontend later without touching the engine.

## Implementation Decisions

The driver spine below was **validated by a throwaway prototype** (kept local, not committed; see
`prototypes/NOTES.md`) against EnergyPlus 25.2 — streaming, pause, and abort all confirmed
working, so these are no longer assumptions.

- **Target EnergyPlus 25.2 (ADR-0004):** locate the install by **numeric** version (parse
  `V25-2-0 -> (25, 2, 0)` — never a lexicographic sort, which would rank `V9-6-0` above
  `V25-2-0`); default to 25.2, `--eplus-root` overrides. Wire `sys.path` and
  `os.add_dll_directory(root)` so `pyenergyplus` imports and `energyplusapi.dll` loads.
- **Driver mode (ADR-0001):** the plotter owns the run — it calls `run_energyplus(state, ["-w",
  epw, "-d", outdir, idf])` via the `pyenergyplus` Runtime API. We do not tail output files or
  embed a plugin in the IDF.
- **Variable source:** parse the model's `Output:Variable` objects for their `(key, variable name,
  frequency)` triples. Because reported variables are computed by EnergyPlus, the **Sampler
  callback** resolves a **Variable handle** for each and reads it directly. (Variables can also be
  requested via `request_variable`, but v1 streams only declared outputs.)
- **`*` key expansion:** on the first ready timestep, expand any `*` key to concrete keys. The
  available `(name, key)` set is exposed after setup via `get_api_data` /
  `list_available_api_data_csv` (277 points in the single-zone prototype run).
- **Sampling cadence:** read all handles at `callback_end_zone_timestep_after_zone_reporting`
  (the zone timestep). The IDF's per-variable reporting frequency is ignored for live reads.
  System/HVAC variables are read at the zone timestep in v1.
- **In-process concurrency (ADR-0002):** `run_energyplus` blocks, so it runs on a background
  worker thread. The Sampler callback (on that thread) guards `api_data_fully_ready`, checks
  `warmup_flag`, builds a **Sample** (sim datetime, warmup flag, per-variable values) and pushes
  it to a thread-safe queue. **No subprocess/IPC in v1.**
- **Run controls (validated):**
  - **Pause/resume** — the Sampler callback blocks on a `threading.Event` (parks the EnergyPlus
    thread between timesteps); resume clears it. Not an EnergyPlus feature — purely our side.
  - **Abort** — the callback checks an abort flag and calls `runtime.stop_simulation(state)`,
    which ends the run promptly (~0.13s in the prototype) and cleanly (exit 0, output files
    written). To abort *while paused*, set the flag and also unblock the pause Event so the parked
    callback wakes, re-checks, and stops.
  - **Restart** — `runtime.clear_callbacks()` + `state_manager.reset_state(state)`.
- **The SampleSink seam (ADR-0003):** the driver emits Samples to a `SampleSink` interface; v1's
  sink is a queue the UI drains. The driver imports no UI code, so a `WebSocketSink` can be added
  later with no engine change.
- **Modules & interfaces:**
  - _EnergyPlus locator_ — resolves the 25.2 install (numeric version), wires `sys.path` + DLL dir.
  - _IDF outputs parser_ — `idf text -> list[(key, name, frequency)]`.
  - _Sample / SampleSink_ — the `Sample` value type and the sink protocol (the seam).
  - _EnergyPlusDriver_ — `start()`, `pause()`, `resume()`, `abort()`, emits Samples to a sink.
  - _Plot UI (pyqtgraph/PySide6)_ — drains the queue on a timer into numpy ring buffers; left/right
    Y-axes, variable show/hide, zoom/pan (built-in), transport buttons; uses autoDownsample.
  - _CLI_ — `eplus-plotter run <model.idf> -w <epw> [-d out] [--eplus-root ...]`.

## Testing Decisions

- **Good test = observable external behavior, not internals.** Assert the **Sample** stream and
  the effects of run-control commands, never private fields or call order.
- **Primary seam — the SampleSink / driver boundary (integration).** Drive a real, short
  EnergyPlus run (a 1-day RunPeriod against a single-zone fixture + the bundled San Francisco EPW)
  with a recording sink, then assert: Samples are emitted; warmup Samples are excluded; a `*` key
  produces one series per key; pause stalls the stream; resume continues it; abort ends the run
  promptly; streamed values match `eplusout.csv` for sampled timesteps. (The prototype is the
  manual precursor of this automated test.)
- **Secondary seam — IDF outputs parser (pure unit).** Feed IDF text (including `*` keys, mixed
  frequencies, comments) and assert the parsed `(key, name, frequency)` list. No EnergyPlus.
- **UI kept thin.** Any view-model logic (axis assignment, ring buffer) is tested as plain
  objects; pyqtgraph/Qt rendering is not unit-tested.
- **Prior art:** none (greenfield). This PRD establishes the "test the host through its SampleSink
  with a real short run" pattern as the reference for future engine tests.

## Out of Scope

- EnergyPlus versions older than 25.2 (pre-`stop_simulation`).
- Web or desktop distribution and the `WebSocketSink` (the seam is built for it, but it is not v1).
- Plugin-mode adapter for plotting runs launched externally (EP-Launch / CBECC / CLI).
- System-timestep (sub-zone-timestep) sampling for HVAC variables.
- Multi-run overlay / comparison, and session save/export.
- Streaming variables the model does **not** declare via `Output:Variable` (would require
  `request_variable` + a discovery UI).

## Further Notes

- **Version coupling:** `pyenergyplus` must match its EnergyPlus install; run under that install's
  `python.exe` (or any Python 3.13) with `os.add_dll_directory(eplus_root)` so the API DLL loads.
- **Prototype verdict (local):** the driver spine was validated against EnergyPlus 25.2 — see
  `prototypes/NOTES.md`. Two findings are baked into the issues: abort needs `stop_simulation`
  (satisfied by the 25.2 target — issue #7) and the locator must sort installs numerically
  (issue #2).
- ADRs to record at implementation: 0001 driver mode, 0002 in-process thread (pause via blocked
  callback / abort via `stop_simulation`), 0003 SampleSink seam for the future web frontend,
  0004 target EnergyPlus 25.2.
