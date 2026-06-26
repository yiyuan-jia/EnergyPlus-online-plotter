"""Drive an EnergyPlus run and stream Samples out across the SampleSink seam.

``run_energyplus`` is a blocking call, so it runs on a background worker thread. The Sampler
callback fires on that thread at the end of each zone timestep; it reads the tracked variables
and hands a :class:`~eplus_plotter.sample.Sample` to the sink. The callback never touches the
UI — everything crosses the thread boundary as Samples.

Run controls (validated by the prototype against EnergyPlus 25.2):

* **pause/resume** — the callback blocks on a ``threading.Event``, parking the run thread
  between timesteps. Not an EnergyPlus feature; purely our side.
* **abort** — the callback calls ``runtime.stop_simulation(state)``, which ends the run
  promptly and cleanly. Aborting while paused also unblocks the event so the parked callback
  wakes, re-checks, and stops.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from typing import Any, Sequence

from .locate import load_api
from .sample import Sample, SampleSink, VariableSpec


class EnergyPlusDriver:
    def __init__(
        self,
        root: Path | str,
        idf: Path | str,
        epw: Path | str,
        outdir: Path | str,
        variables: Sequence[VariableSpec],
        sink: SampleSink,
        *,
        extra_args: Sequence[str] = (),
        throttle: float = 0.0,
    ) -> None:
        self._root = Path(root)
        self._idf = str(idf)
        self._epw = str(epw)
        self._outdir = str(outdir)
        self._variables = list(variables)
        self._sink = sink
        self._extra_args = list(extra_args)
        self._throttle = throttle

        self._resume = threading.Event()
        self._resume.set()  # set == running, cleared == paused
        self._abort = threading.Event()

        self._handles: dict[VariableSpec, int] = {}
        self._resolved = False
        self._thread: threading.Thread | None = None
        self._exit_code: int | None = None
        self._error: Exception | None = None
        self._api: Any = None  # EnergyPlusAPI, created on the worker thread (untyped native lib)

    # -- lifecycle -----------------------------------------------------------------------

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="eplus-worker", daemon=True)
        self._thread.start()

    def join(self, timeout: float | None = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def exit_code(self) -> int | None:
        return self._exit_code

    @property
    def error(self) -> Exception | None:
        """The exception that ended the run, if it failed on the worker thread."""
        return self._error

    # -- run controls --------------------------------------------------------------------

    def pause(self) -> None:
        self._resume.clear()

    def resume(self) -> None:
        self._resume.set()

    def abort(self) -> None:
        self._abort.set()
        self._resume.set()  # wake the callback if it is parked in a pause

    # -- worker thread -------------------------------------------------------------------

    def _run(self) -> None:
        try:
            api = load_api(self._root)
            self._api = api
            state = api.state_manager.new_state()
            for spec in self._variables:
                api.exchange.request_variable(state, spec.name, spec.key)
            api.runtime.callback_end_zone_timestep_after_zone_reporting(state, self._on_timestep)
            args = ["-d", self._outdir, "-w", self._epw, *self._extra_args, self._idf]
            self._exit_code = api.runtime.run_energyplus(state, args)
        except Exception as exc:  # surface worker-thread failures instead of dying silently
            self._error = exc
            print(f"[eplus-plotter] run failed: {exc!r}", file=sys.stderr)

    def _resolve_handles(self, state: Any) -> None:
        ex = self._api.exchange
        missing = []
        for spec in self._variables:
            handle = ex.get_variable_handle(state, spec.name, spec.key)
            self._handles[spec] = handle
            if handle < 0:
                missing.append(spec)
        self._resolved = True
        if missing:
            names = ", ".join(str(s) for s in missing)
            print(
                f"[eplus-plotter] warning: variable not found, will not plot: {names}",
                file=sys.stderr,
            )

    def _on_timestep(self, state: Any) -> None:
        ex = self._api.exchange
        # Abort takes priority and must work even before data is ready (e.g. during warmup).
        if self._abort.is_set():
            self._api.runtime.stop_simulation(state)
            return
        if not ex.api_data_fully_ready(state):
            return
        self._resume.wait()  # park here while paused
        if self._abort.is_set():  # may have been set while we were parked
            self._api.runtime.stop_simulation(state)
            return

        if not self._resolved:
            self._resolve_handles(state)

        values = {
            spec: ex.get_variable_value(state, h)
            for spec, h in self._handles.items()
            if h >= 0
        }
        self._sink.emit(
            Sample(
                day_of_year=ex.day_of_year(state),
                current_time=ex.current_time(state),
                sim_time_hours=ex.current_sim_time(state),
                is_warmup=ex.warmup_flag(state),
                values=values,
            )
        )
        if self._throttle:
            time.sleep(self._throttle)
