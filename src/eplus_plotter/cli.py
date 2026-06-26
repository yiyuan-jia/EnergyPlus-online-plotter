"""Command line entry point: ``eplus-plotter run <model.idf> -w <weather.epw>``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .idf_outputs import parse_output_variables
from .locate import locate_energyplus


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
        "--var",
        action="append",
        metavar="NAME",
        help="only stream the named Output:Variable(s); repeatable (default: all declared)",
    )
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
    variables = parse_output_variables(args.idf.read_text())
    if args.var:
        wanted = {name.lower() for name in args.var}
        variables = [spec for spec in variables if spec.name.lower() in wanted]
        if not variables:
            print(
                f"[eplus-plotter] none of {args.var} match an Output:Variable in {args.idf}",
                file=sys.stderr,
            )
            return 2
    if not variables:
        print(
            f"[eplus-plotter] {args.idf} declares no Output:Variable objects to plot.",
            file=sys.stderr,
        )
        return 2
    args.outdir.mkdir(parents=True, exist_ok=True)

    # Import Qt/UI lazily so the package imports (and most tests) don't require a display.
    from pyqtgraph.Qt import QtWidgets

    from .driver import EnergyPlusDriver
    from .ui import PlotWindow, QueueSink

    sink = QueueSink()
    driver = EnergyPlusDriver(
        root, args.idf, args.weather, args.outdir, variables, sink, throttle=args.throttle
    )

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    window = PlotWindow(driver, sink)
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
