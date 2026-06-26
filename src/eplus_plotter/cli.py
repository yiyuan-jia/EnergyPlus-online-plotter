"""Command line entry point: ``eplus-plotter run <model.idf> -w <weather.epw>``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .locate import locate_energyplus
from .sample import VariableSpec

# v1 streams a single hardcoded variable; declared-Output:Variable parsing is a later slice.
SITE_DRYBULB = VariableSpec("Site Outdoor Air Drybulb Temperature", "Environment")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="eplus-plotter", description="Live-plot a running EnergyPlus simulation."
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="run a model and plot it live")
    run.add_argument("idf", type=Path, help="EnergyPlus model (.idf)")
    run.add_argument("-w", "--weather", type=Path, required=True, help="weather file (.epw)")
    run.add_argument("-d", "--outdir", type=Path, default=Path("eplus-out"), help="output dir")
    run.add_argument("--eplus-root", type=Path, default=None, help="EnergyPlus install to use")
    run.add_argument(
        "--throttle",
        type=float,
        default=0.0,
        help="seconds to sleep per timestep (slow a fast sim down so you can watch it)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    root = locate_energyplus(args.eplus_root)
    args.outdir.mkdir(parents=True, exist_ok=True)

    # Import Qt/UI lazily so the package imports (and most tests) don't require a display.
    from pyqtgraph.Qt import QtWidgets

    from .driver import EnergyPlusDriver
    from .ui import PlotWindow, QueueSink

    variables = [SITE_DRYBULB]
    sink = QueueSink()
    driver = EnergyPlusDriver(
        root, args.idf, args.weather, args.outdir, variables, sink, throttle=args.throttle
    )

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    window = PlotWindow(driver, sink, variables)
    window.resize(900, 600)
    window.show()

    driver.start()
    try:
        exit_code = app.exec()
    finally:
        driver.abort()
        driver.join(timeout=10)
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
