"""Deprecated - use :mod:`tools.system_utilities` instead."""

import sys

from .system_utilities import cli_main, httpx, create_ticket

sys = sys  # re-export for tests

if __name__ == "__main__":
    cli_main()
