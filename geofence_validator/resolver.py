# -*- coding: utf-8 -*-
"""
resolver.py - IP to Country Resolution Abstraction and Implementation.

This module provides the system for resolving an IP address to its corresponding
ISO 3166-1 alpha-2 country code.

The default `InMemoryResolver` is designed for production use by loading its
data from a file. Its data-loading strategy is as follows:
1.  If a `data_file_path` is provided during initialization, it will attempt to
    load data from that external CSV file. This allows users to supply their
    own, more comprehensive or up-to-date IP-to-country mappings.
2.  If no path is provided, it uses the `importlib.resources` module to
    reliably access the `ip_ranges.csv` file that is bundled *inside* the
    installed package. This ensures the library works out-of-the-box with
    zero configuration after a `pip install`.

This "batteries-included but extensible" pattern is a robust design for
distributable Python libraries.
"""
from __future__ import annotations

import abc
import csv
import ipaddress
import logging
from typing import IO, Final, Iterable, List, NamedTuple, Optional, Union

# Use the modern way to access package data files.
# It is robust against how the package is installed (wheel, egg, editable).
from importlib import resources

from .errors import (
    IPAddressNotFoundError,
    InvalidIPAddressError,
    NonPublicIPAddressError,
    ResolverInitializationError,
)

IPAddress = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]
IPNetwork = Union[ipaddress.IPv4Network, ipaddress.IPv6Network]

logger = logging.getLogger(__name__)

# The filename of the default, bundled data source.
_DEFAULT_DATA_FILENAME: Final[str] = "ip_ranges.csv"


# ==============================================================================
# Abstract Base Class (Unchanged)
# ==============================================================================
class Resolver(abc.ABC):
    """Abstract interface for an IP-to-country resolver."""

    @abc.abstractmethod
    def resolve(self, ip_string: str) -> str:
        """Resolves a given IP address string to a two-letter country code."""
        raise NotImplementedError


# ==============================================================================
# In-Memory Concrete Implementation (Rewritten for Data Loading)
# ==============================================================================

class _CompiledRange(NamedTuple):
    """Internal representation of a compiled network range and its country."""
    network: IPNetwork
    country_code: str


class InMemoryResolver(Resolver):
    """
    A zero-dependency, in-memory IP to country resolver that loads from a file.

    This resolver populates its data from a CSV file containing `CIDR,country`
    mappings. It can use a user-provided file or the default one bundled with
    the library.
    """

    def __init__(
        self,
        *,
        data_file_path: Optional[str] = None,
        internal_logger: Optional[logging.Logger] = None,
    ):
        """
        Initializes the resolver and loads/compiles the IP ranges from a source.

        Args:
            data_file_path: Optional path to a custom CSV data file. If None,
                            the default `ip_ranges.csv` bundled with the
                            package will be used.
            internal_logger: An optional logger instance.

        Raises:
            ResolverInitializationError: If the data source cannot be found,
                                         is unreadable, or contains invalid data.
        """
        self._log = internal_logger or logger
        self._compiled_ranges: List[_CompiledRange] = []

        try:
            if data_file_path:
                self._log.info("Loading IP data from user-provided file: %s", data_file_path)
                with open(data_file_path, "r", encoding="utf-8") as f:
                    self._load_data_from_stream(f)
            else:
                self._log.info("Loading IP data from bundled package resource.")
                # This is the correct, modern way to access package data.
                with resources.files("geofence_validator.data").joinpath(
                    _DEFAULT_DATA_FILENAME
                ).open("r", encoding="utf-8") as f:
                    self._load_data_from_stream(f)

        except FileNotFoundError as e:
            msg = f"Data file not found at path: {data_file_path}"
            self._log.error(msg)
            raise ResolverInitializationError(details=msg) from e
        except Exception as e:
            # Catch any other potential errors during init (parsing, etc.)
            msg = f"Failed to initialize resolver: {e}"
            self._log.critical(msg, exc_info=True)
            raise ResolverInitializationError(details=msg) from e

        if not self._compiled_ranges:
            raise ResolverInitializationError(
                "Resolver initialized, but no valid IP ranges were loaded. "
                "The data source might be empty or malformed."
            )

        self._log.info(
            "InMemoryResolver initialized with %d compiled IP ranges.",
            len(self._compiled_ranges)
        )

    def _load_data_from_stream(self, stream: IO[str]) -> None:
        """Helper to parse a CSV data stream and compile ranges."""
        reader = csv.reader(line for line in stream if not line.strip().startswith("#"))
        for i, row in enumerate(reader):
            line_num = i + 1
            if not row:  # Skip empty lines
                continue
            if len(row) != 2:
                raise ResolverInitializationError(
                    f"Invalid data format on line {line_num}: Expected 2 columns, got {len(row)}"
                )

            cidr_str, country = row[0].strip(), row[1].strip()
            if not cidr_str or not country:
                 raise ResolverInitializationError(f"Empty CIDR or country on line {line_num}")

            try:
                network = ipaddress.ip_network(cidr_str)
                self._compiled_ranges.append(
                    _CompiledRange(network=network, country_code=country)
                )
            except ValueError as e:
                raise ResolverInitializationError(
                    f"Invalid CIDR notation '{cidr_str}' on line {line_num}: {e}"
                )

    def _validate_and_parse_ip(self, ip_string: str) -> IPAddress:
        """Parses and validates an IP string, checking for non-public addresses."""
        try:
            ip_obj = ipaddress.ip_address(ip_string)
        except ValueError:
            self._log.warning("Invalid IP address string received: '%s'", ip_string)
            raise InvalidIPAddressError(invalid_ip=ip_string)

        if not ip_obj.is_global:
            reason = "non-global"
            if ip_obj.is_loopback: reason = "loopback"
            elif ip_obj.is_link_local: reason = "link-local"
            elif ip_obj.is_unspecified: reason = "unspecified"
            elif ip_obj.is_private: reason = "private (RFC 1918)"
            
            self._log.warning(
                "Attempted to resolve non-public IP '%s' (%s)", ip_string, reason
            )
            raise NonPublicIPAddressError(ip_address=ip_string, reason=reason)

        return ip_obj

    def resolve(self, ip_string: str) -> str:
        """Resolves an IP by checking it against the compiled in-memory CIDR ranges."""
        ip_obj = self._validate_and_parse_ip(ip_string)
        self._log.debug("Attempting to resolve IP address: %s", ip_string)

        for item in self._compiled_ranges:
            if ip_obj in item.network:
                self._log.info(
                    "Resolved IP '%s' to country '%s' via network '%s'.",
                    ip_string,
                    item.country_code,
                    item.network,
                )
                return item.country_code

        self._log.warning(
            "IP address '%s' is public but was not found in any known range.",
            ip_string,
        )
        raise IPAddressNotFoundError(ip_address=ip_string)