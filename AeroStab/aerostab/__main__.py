"""AeroStab entry point."""

from __future__ import annotations

import argparse
import logging
import sys

from aerostab.config import load_config
from aerostab.runtime import AeroStabRuntime
from aerostab.state import SharedState
from aerostab.web import start_web_server


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AeroStab optical navigation")
    parser.add_argument("-c", "--config", help="Path to YAML config")
    parser.add_argument("--simulate", action="store_true", help="Synthetic camera (no hardware)")
    parser.add_argument("--no-web", action="store_true", help="Disable web UI")
    parser.add_argument("--no-mavlink", action="store_true", help="Disable MAVLink output")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    setup_logging(args.verbose)
    config = load_config(args.config)
    if args.simulate:
        config.runtime.simulate = True
    if args.no_mavlink:
        config.mavlink.enabled = False

    shared = SharedState()
    runtime = AeroStabRuntime(config, shared)

    if config.web.enabled and not args.no_web:
        start_web_server(shared, config)
        logging.getLogger(__name__).info(
            "Web UI http://%s:%d", config.web.host, config.web.port
        )

    runtime.run_loop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
