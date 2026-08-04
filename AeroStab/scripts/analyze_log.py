#!/usr/bin/env python3
"""CLI wrapper — prefer ``python -m aerostab.log_analyzer`` or ``aerostab-analyze``."""

from aerostab.log_analyzer import cli_main

if __name__ == "__main__":
    raise SystemExit(cli_main())
