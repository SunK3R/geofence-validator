# -*- coding: utf-8 -*-
"""
geofence_validator.__main__ - Command-Line Interface for quick validations.

This module provides a command-line entry point to the geofence-validator
library, allowing for quick, one-off checks without writing a Python script.
It is a demonstration of the library's core features, including custom
resolvers and optional rich logging.

While this CLI is a useful utility, the recommended way to use the library
programmatically is by importing and using the `Validator` class from the `core`
module, as it is more performant for repeated checks.

**Usage Examples:**

1.  Basic whitelist check (will use the bundled data):
    $ python -m geofence_validator 8.8.8.8 whitelist US CA

2.  Basic blacklist check:
    $ python -m geofence_validator 78.46.10.20 blacklist DE

3.  Enable verbose, rich-colored logging:
    $ python -m geofence_validator --verbose 1.1.1.1 whitelist JP AU

4.  Use a custom, user-provided data file:
    $ python -m geofence_validator --data-file /path/to/my_ips.csv 8.8.8.8 whitelist US
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import List, Optional, Sequence

from . import __version__, errors
from .core import Validator
from .logger import enable_debugging
from .resolver import InMemoryResolver


def create_argument_parser() -> argparse.ArgumentParser:
    """Creates and configures the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="geofence_validator",
        description=(
            "A command-line tool to perform a geofence validation for a given IP address. "
            f"(v{__version__})"
        ),
        epilog="For programmatic use, import and use the 'Validator' class.",
    )

    parser.add_argument(
        "ip_address",
        metavar="IP_ADDRESS",
        type=str,
        help="The IPv4 or IPv6 address to validate.",
    )
    parser.add_argument(
        "policy_rule",
        metavar="POLICY_RULE",
        type=str,
        choices=["whitelist", "blacklist"],
        help="The policy rule to apply. Must be 'whitelist' or 'blacklist'.",
    )
    parser.add_argument(
        "countries",
        metavar="COUNTRY_CODE",
        type=str,
        nargs="+",
        help="One or more two-letter ISO 3166-1 alpha-2 country codes.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose, rich-formatted debug logging to stderr.",
    )
    parser.add_argument(
        "--data-file",
        metavar="PATH",
        type=str,
        help=(
            "Optional path to a custom CSV data file for IP-to-country resolution. "
            "If not provided, the bundled data is used."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """
    Main entry point for the command-line interface.

    Args:
        argv: An optional sequence of command-line arguments. If None,
              `sys.argv` is used.

    Returns:
        An exit code:
        - 0: The IP was ALLOWED.
        - 1: The IP was DENIED.
        - 2: An error occurred during validation (e.g., bad input, file not found).
    """
    parser = create_argument_parser()
    args = parser.parse_args(argv)

    if args.verbose:
        # Showcase our beautiful, optional logging feature.
        enable_debugging()

    log = logging.getLogger(__name__)  # Get logger after setup
    log.debug("CLI arguments parsed: %s", args)

    try:
        # 1. Set up the resolver if a custom data file is provided.
        custom_resolver = None
        if args.data_file:
            log.info("Using custom data file from: %s", args.data_file)
            custom_resolver = InMemoryResolver(data_file_path=args.data_file)

        # 2. Create the Validator instance. This is the core engine.
        # We ensure country codes are uppercase for robustness.
        countries_set = {c.upper() for c in args.countries}
        validator = Validator(
            policy_rule=args.policy_rule,
            countries=countries_set,
            custom_resolver=custom_resolver,
        )

        # 3. Perform the check.
        is_allowed = validator.check(args.ip_address)

        # 4. Report the result clearly to stdout.
        if is_allowed:
            print("Result: ALLOWED")
            return 0  # Success (Allowed)
        else:
            print("Result: DENIED")
            return 1  # Success (Denied)

    except errors.GeofenceError as e:
        # Handle all known, predictable errors from our library gracefully.
        print(f"Error: {e}", file=sys.stderr)
        log.debug("GeofenceError caught", exc_info=True)
        return 2
    except Exception as e:
        # Handle unexpected errors.
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        log.critical("An uncaught exception occurred in the CLI.", exc_info=True)
        return 2


if __name__ == "__main__":
    # This allows the script to be executed directly, in addition to
    # `python -m geofence_validator`.
    sys.exit(main())