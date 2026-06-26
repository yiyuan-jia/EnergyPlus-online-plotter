# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

**Greenfield / empty repo.** There is no source code, build tooling, or tests yet. The
sections below describe the *intended* design so the first scaffolding lands in the right
shape. Update this file (especially the Commands section) as soon as real code exists —
do not leave invented commands here.

## What this is

An "online plotter" for EnergyPlus, modeled on the **Online Plotter** in TRNSYS: a tool
that displays simulation output as time-series plots, ideally **live while the simulation
runs**, with variables assignable to left/right Y-axes and zoom/pan over the run period.

The defining requirement (chosen for this project) is **live/streaming** plotting — render
output in near-real-time during a running EnergyPlus simulation, not just post-mortem from
result files.

## The core architectural constraint: how to get live data out of EnergyPlus

This is the part that requires understanding before writing any code, because it dictates
the rest of the architecture.

EnergyPlus does **not** reliably flush `eplusout.csv` / `eplusout.eso` / `eplusout.sql`
mid-run, so tailing output files is not a viable path to live data. The supported way to
observe values during a simulation is the **EnergyPlus Runtime API** (the `pyenergyplus`
Python package that ships inside every EnergyPlus install, plus an equivalent C API).

The runtime API drives a simulation from your own process and fires callbacks at defined
points each timestep. The data-exchange pattern is:

1. Before the run, **request** each output variable you intend to read
   (`exchange.request_variable(state, "<Variable Name>", "<Key/Component>")`). EnergyPlus
   only computes a variable if it is reported or requested.
2. Register a callback at the right timing point (e.g.
   `runtime.callback_end_zone_timestep_after_zone_reporting`).
3. Inside the callback, guard on `exchange.api_data_fully_ready(state)` and check
   `exchange.warmup_flag(state)` (skip or label warmup timesteps), then resolve a
   **handle** once (`exchange.get_variable_handle(...)`) and read
   `exchange.get_variable_value(state, handle)`. Handles are only valid after data is
   ready; cache them, don't re-resolve every timestep.
4. Pair each value with sim time (`exchange.current_sim_time`, `day_of_year`,
   `current_time`, etc.).

**Key consequence:** the callback runs *inside* EnergyPlus's run thread. Streaming to any
UI means handing samples off across a thread/process boundary — a queue, websocket, or IPC
channel — never doing UI work inside the callback. Whatever stack is chosen, there will be
an **EnergyPlus host** (Python, owning the API + simulation) feeding a **plot frontend**.

Treat the exact API method names/signatures above as version-sensitive: verify against the
`pyenergyplus` in the user's installed EnergyPlus before relying on them.

## Stack — undecided (document both)

The plotting/UI stack is intentionally open. The live-streaming requirement biases the
*backend* toward Python regardless, since the runtime API is C/Python:

- **Web (browser frontend + Python host):** Python process runs EnergyPlus via
  `pyenergyplus` and streams samples over a websocket to a browser app (Plotly.js /
  ECharts). Best fit for an "online" tool; clean thread boundary between sim and UI.
- **Desktop (Tauri/Electron + Python sidecar):** closest to the TRNSYS Online Plotter
  feel, with local filesystem access to IDF/EPW and a bundled EnergyPlus.

Until the user picks one, keep new code split along the host ↔ frontend boundary so either
choice remains cheap. When the decision is made, record it here and delete the unused branch.

## EnergyPlus domain notes relevant to plotting

- Variables are identified by **(variable name, key)** — e.g. `("Zone Mean Air Temperature",
  "ZONE1")`. The same variable name exists for many keys (zones, surfaces, systems).
- **Reporting frequency** matters: timestep / hourly / daily / monthly / runperiod. Live
  plotting works at the zone/system timestep; coarser frequencies emit far fewer points.
- A run has **warmup** days that repeat the first design day — these are normally excluded
  from plots or visually distinguished.
- Inputs are an **IDF** (or epJSON) model file plus an **EPW** weather file; output goes to
  a `-d <outdir>`. The plotter must let the user point at these.

## Commands

_None yet — repo is empty._ Add build/run/lint/test commands here the moment scaffolding
exists. When you do, include how to run a **single** test, not just the whole suite.

## Agent skills

### Issue tracker

Issues and PRDs live in this repo's GitHub Issues (via the `gh` CLI). External PRs are **not** a triage surface. See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary — each label string equals its canonical role (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
