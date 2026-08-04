"""AeroStab entry point."""

from __future__ import annotations

import argparse
import logging
import os
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
    parser.add_argument("-c", "--config", help="YAML config path")
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--sitl", action="store_true", help="Use config/sitl.yaml (TCP MAVLink + synthetic camera)")
    parser.add_argument("--no-web", action="store_true")
    parser.add_argument("--no-mavlink", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    setup_logging(args.verbose)
    config_path = args.config or os.environ.get("AEROSTAB_CONFIG", "")
    if not config_path:
        from pathlib import Path

        for candidate in (
            "/etc/aerostab/config.yaml",
            str(Path(__file__).resolve().parents[1] / "config" / "default.yaml"),
        ):
            if Path(candidate).exists():
                config_path = candidate
                break
        else:
            config_path = str(Path(__file__).resolve().parents[1] / "config" / "default.yaml")

    if args.sitl:
        from pathlib import Path

        sitl_cfg = Path(__file__).resolve().parents[1] / "config" / "sitl.yaml"
        config_path = str(sitl_cfg)
        config = load_config(config_path)
        config.runtime.simulate = True
    else:
        config = load_config(config_path)
    if args.simulate:
        config.runtime.simulate = True
    if args.no_mavlink:
        config.mavlink.enabled = False

    shared = SharedState()
    runtime = AeroStabRuntime(config, shared, config_path=config_path)

    if config.web.enabled and not args.no_web:
        start_web_server(shared, config, runtime, config_path)
        logging.getLogger(__name__).info("Web http://%s:%d", config.web.host, config.web.port)

    runtime.run_loop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
