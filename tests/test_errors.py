# -*- coding: utf-8 -*-
"""
test_errors.py - Unit Tests for the Custom Exception Classes.

This test suite is focused on verifying the intrinsic properties of the custom
exception classes defined in `geofence_validator.errors`.

The tests ensure that:
1.  **The Exception Hierarchy is Correct**: Each exception inherits from the
    correct base class (e.g., `InvalidIPAddressError` is a subclass of
    `ValidationError`, which is a subclass of `GeofenceError`). This is critical
    for allowing users to perform fine-grained error handling.

2.  **Contextual Attributes are Stored Correctly**: Each exception class is
    instantiated, and we assert that the context-specific data passed to its
    constructor (like the invalid IP or country code) is correctly stored as an
    attribute on the exception object.

3.  **Error Messages are Formatted Correctly**: We verify that the string
    representation of each exception object is a clear, user-friendly message
    that includes the relevant contextual data.

This suite does not test *when* these exceptions are raised, as that is the
responsibility of the tests for the modules that raise them (e.g., `test_core`,
`test_resolver`). This is purely a unit test of the error classes themselves.
"""
import pytest

from geofence_validator import errors

# ==============================================================================
# Test Cases for Exception Hierarchy
# ==============================================================================

def test_exception_hierarchy():
    """
    Verifies the entire class inheritance structure of the custom exceptions.
    This test serves as a "living document" of the error hierarchy.
    """
    assert issubclass(errors.ValidationError, errors.GeofenceError)
    assert issubclass(errors.ResolutionError, errors.GeofenceError)
    assert issubclass(errors.PolicyError, errors.GeofenceError)
    assert issubclass(errors.ConfigurationError, errors.GeofenceError)

    # Validation Subclasses
    assert issubclass(errors.InvalidIPAddressError, errors.ValidationError)
    assert issubclass(errors.NonPublicIPAddressError, errors.ValidationError)
    assert issubclass(errors.InvalidCountryCodeError, errors.ValidationError)
    assert issubclass(errors.InvalidPolicyRuleError, errors.ValidationError)

    # Resolution Subclasses
    assert issubclass(errors.IPResolutionFailedError, errors.ResolutionError)
    assert issubclass(errors.IPAddressNotFoundError, errors.ResolutionError)

    # Policy Subclasses
    assert issubclass(errors.InvalidPolicyDefinitionError, errors.PolicyError)

    # Configuration Subclasses
    assert issubclass(errors.ResolverInitializationError, errors.ConfigurationError)


# ==============================================================================
# Test Cases for Individual Exception Classes
# ==============================================================================

class TestExceptionProperties:
    """
    Tests that each exception class correctly stores its attributes and
    formats its error message.
    """

    def test_invalid_ip_address_error(self):
        """Tests InvalidIPAddressError."""
        bad_ip = "999.999.999.999"
        e = errors.InvalidIPAddressError(invalid_ip=bad_ip)
        assert e.invalid_ip == bad_ip
        assert bad_ip in str(e)
        assert "not a valid" in str(e)

    def test_non_public_ip_address_error(self):
        """Tests NonPublicIPAddressError."""
        ip = "127.0.0.1"
        reason = "loopback"
        e = errors.NonPublicIPAddressError(ip_address=ip, reason=reason)
        assert e.ip_address == ip
        assert e.reason == reason
        assert ip in str(e)
        assert reason in str(e)
        assert "non-public" in str(e)

    def test_invalid_country_code_error(self):
        """Tests InvalidCountryCodeError."""
        bad_code = "USA"
        e = errors.InvalidCountryCodeError(invalid_code=bad_code)
        assert e.invalid_code == bad_code
        assert bad_code in str(e)
        assert "two-letter" in str(e)

    def test_invalid_policy_rule_error(self):
        """Tests InvalidPolicyRuleError."""
        bad_rule = "maybe"
        supported = ("whitelist", "blacklist")
        e = errors.InvalidPolicyRuleError(
            unsupported_rule=bad_rule, supported_rules=supported
        )
        assert e.unsupported_rule == bad_rule
        assert e.supported_rules == supported
        assert bad_rule in str(e)
        assert "whitelist" in str(e)
        assert "blacklist" in str(e)

    def test_ip_resolution_failed_error(self):
        """Tests IPResolutionFailedError."""
        ip = "8.8.8.8"
        details = "DNS timed out"
        e = errors.IPResolutionFailedError(ip_address=ip, details=details)
        assert e.ip_address == ip
        assert e.details == details
        assert ip in str(e)
        assert details in str(e)
        assert "Failed to resolve" in str(e)

    def test_ip_address_not_found_error(self):
        """Tests IPAddressNotFoundError."""
        ip = "99.99.99.99"
        e = errors.IPAddressNotFoundError(ip_address=ip)
        assert e.ip_address == ip
        assert ip in str(e)
        assert "not found" in str(e)

    def test_invalid_policy_definition_error(self):
        """Tests InvalidPolicyDefinitionError."""
        reason = "Whitelist cannot be empty"
        e = errors.InvalidPolicyDefinitionError(reason=reason)
        assert e.reason == reason
        assert reason in str(e)
        assert "Invalid policy definition" in str(e)

    def test_resolver_initialization_error(self):
        """Tests ResolverInitializationError."""
        details = "Database file is corrupted"
        e = errors.ResolverInitializationError(details=details)
        assert e.details == details
        assert details in str(e)
        assert "Failed to initialize" in str(e)