# -*- coding: utf-8 -*-
"""
errors.py - Custom Exception Hierarchy for the Geofence Validator Library.

This module defines a structured set of custom exceptions that are raised by
the geofence_validator library. By providing a clear hierarchy, consuming code
can perform fine-grained error handling, distinguishing between different
classes of failures such as input validation, IP resolution issues, and policy
configuration problems.

All exceptions in this library inherit from a single base class, `GeofenceError`.
This allows users to catch any library-specific error with a single
`except GeofenceError:` block if they choose to.

The hierarchy is designed to be both informative and actionable:
- GeofenceError (Base for all library exceptions)
  - ValidationError (Category for malformed or invalid user inputs)
    - InvalidIPAddressError (Input is not a valid IPv4 or IPv6 address)
    - NonPublicIPAddressError (IP is valid but reserved, private, or loopback)
    - InvalidCountryCodeError (Country code is not a valid ISO 3166-1 alpha-2)
    - InvalidPolicyRuleError (Policy rule string is not recognized)
  - ResolutionError (Category for failures during the IP-to-country lookup)
    - IPResolutionFailedError (A generic failure occurred in the resolver)
    - IPAddressNotFoundError (The IP is valid but not found in the lookup data)
  - PolicyError (Category for logical errors in policy definition)
    - InvalidPolicyDefinitionError (A policy is configured incorrectly)
  - ConfigurationError (Category for setup or initialization problems)
    - ResolverInitializationError (The resolver could not be initialized)

Each exception class carries context-specific information, such as the invalid
value that caused the error, making debugging and logging far more effective.
"""

from __future__ import annotations

# ==============================================================================
# Base Exception
# ==============================================================================

class GeofenceError(Exception):
    """
    Base class for all custom exceptions raised by the geofence-validator library.

    Catching this exception will handle any error originating from this library,
    allowing for robust, library-specific error handling.
    """
    def __init__(self, message: str):
        """Initializes the base geofence error."""
        super().__init__(message)


# ==============================================================================
# Input Validation Error Hierarchy
# ==============================================================================

class ValidationError(GeofenceError):
    """
    Base class for errors related to invalid user-provided input.

    This category of exceptions is raised when the inputs to a validation
    function (like an IP address, country code, or policy rule) fail
    syntactic or semantic checks before any resolution is attempted.
    """
    def __init__(self, message: str):
        """Initializes the base validation error."""
        super().__init__(message)


class InvalidIPAddressError(ValidationError):
    """
    Raised when a provided string is not a valid IPv4 or IPv6 address.

    This indicates a fundamental syntax error in the IP address string itself,
    making it impossible to parse.

    Attributes:
        invalid_ip (str): The malformed IP string that caused the error.
    """
    def __init__(self, invalid_ip: str):
        self.invalid_ip = invalid_ip
        message = (
            f"The provided string '{invalid_ip}' is not a valid IPv4 or "
            f"IPv6 address."
        )
        super().__init__(message)


class NonPublicIPAddressError(ValidationError):
    """
    Raised when a valid IP address falls within a reserved range.

    This includes private networks (RFC 1918), loopback addresses, link-local
    addresses, or other special-use IP blocks that cannot be geolocated.

    Attributes:
        ip_address (str): The IP address that is non-public.
        reason (str): The reason why the IP is considered non-public.
    """
    def __init__(self, ip_address: str, reason: str):
        self.ip_address = ip_address
        self.reason = reason
        message = (
            f"The IP address '{ip_address}' is a non-public address "
            f"({reason}) and cannot be geolocated."
        )
        super().__init__(message)


class InvalidCountryCodeError(ValidationError):
    """
    Raised when a country code is not a valid ISO 3166-1 alpha-2 string.

    The library strictly expects two-letter, uppercase country codes (e.g., 'US',
    'GB', 'DE'). Any other format is considered invalid.

    Attributes:
        invalid_code (str): The invalid country code string provided.
    """
    def __init__(self, invalid_code: str):
        self.invalid_code = invalid_code
        message = (
            f"The country code '{invalid_code}' is invalid. It must be a "
            f"two-letter, uppercase ISO 3166-1 alpha-2 code (e.g., 'US', 'DE')."
        )
        super().__init__(message)


class InvalidPolicyRuleError(ValidationError):
    """
    Raised when the specified policy rule is not supported.

    The library supports a fixed set of policy rules (e.g., 'whitelist',
    'blacklist'). This error occurs if an unknown rule is provided.

    Attributes:
        unsupported_rule (str): The rule that is not recognized.
        supported_rules (tuple[str, ...]): A tuple of valid rule strings.
    """
    def __init__(self, unsupported_rule: str, supported_rules: tuple[str, ...]):
        self.unsupported_rule = unsupported_rule
        self.supported_rules = supported_rules
        message = (
            f"Policy rule '{unsupported_rule}' is not supported. "
            f"Available rules are: {', '.join(supported_rules)}."
        )
        super().__init__(message)


# ==============================================================================
# IP Resolution Error Hierarchy
# ==============================================================================

class ResolutionError(GeofenceError):
    """
    Base class for errors that occur during the IP-to-country resolution phase.

    These errors indicate that while the input IP address was valid, the
    system failed to determine its country of origin.
    """
    def __init__(self, message: str):
        """Initializes the base resolution error."""
        super().__init__(message)


class IPResolutionFailedError(ResolutionError):
    """
    Raised for a generic failure within the IP-to-country resolver.

    This could be due to an internal error in the resolver's logic or an
    inability to access its underlying data source.

    Attributes:
        ip_address (str): The IP address that failed to be resolved.
        details (str): A message describing the nature of the internal failure.
    """
    def __init__(self, ip_address: str, details: str):
        self.ip_address = ip_address
        self.details = details
        message = (
            f"Failed to resolve country for IP address '{ip_address}'. "
            f"Details: {details}"
        )
        super().__init__(message)


class IPAddressNotFoundError(ResolutionError):
    """
    Raised when an IP address could not be found in the resolution database.

    This is distinct from a resolution failure. It means the lookup process
    worked correctly, but no geographic data exists for the given IP address.
    This can happen for new, unassigned, or obscure IP blocks.

    Attributes:
        ip_address (str): The IP address for which no data was found.
    """
    def __init__(self, ip_address: str):
        self.ip_address = ip_address
        message = (
            f"The IP address '{ip_address}' was not found in the geographic "
            f"database."
        )
        super().__init__(message)


# ==============================================================================
# Policy and Configuration Error Hierarchy
# ==============================================================================

class PolicyError(GeofenceError):
    """
    Base class for errors related to policy definition or logic.
    """
    def __init__(self, message: str):
        """Initializes the base policy error."""
        super().__init__(message)


class InvalidPolicyDefinitionError(PolicyError):
    """
    Raised when a policy object is constructed with invalid parameters.

    For example, creating a whitelist policy with an empty list of countries
    might be considered an invalid definition.

    Attributes:
        reason (str): A description of why the policy definition is invalid.
    """
    def __init__(self, reason: str):
        self.reason = reason
        message = f"Invalid policy definition: {reason}"
        super().__init__(message)


class ConfigurationError(GeofenceError):
    """
    Base class for errors related to library setup or initialization.
    """
    def __init__(self, message: str):
        """Initializes the base configuration error."""
        super().__init__(message)


class ResolverInitializationError(ConfigurationError):
    """
    Raised when the IP-to-country resolver fails to initialize.

    This is a critical startup error, for instance, if a required local
    database file is missing, corrupt, or cannot be loaded.

    Attributes:
        details (str): A message explaining the cause of the initialization failure.
    """
    def __init__(self, details: str):
        self.details = details
        message = f"Failed to initialize the IP resolver: {details}"
        super().__init__(message)