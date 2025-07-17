# -*- coding: utf-8 -*-
"""
test_core.py - Unit and Integration Tests for the Core Validation Logic.

This suite validates the `core` module, which orchestrates the policy and
resolver components.

Testing Strategy:
1.  **Mocking the Resolver**: We use a mock resolver (`MockResolver`) to test
    the `Validator` class and `is_ip_allowed` function in isolation. This allows
    us to simulate any possible outcome from the resolution step (e.g., finding
    a country, not finding one, raising a specific error) without any dependency
    on the actual `InMemoryResolver` or the file system. This ensures our tests
    are fast, deterministic, and true unit tests of the orchestration logic.

2.  **Testing Both APIs**: Separate test classes are used for the `Validator`
    class and the `is_ip_allowed` functional wrapper to ensure both public
    APIs are working as intended.

3.  **Thread-Safety Verification**: A dedicated test, `test_default_resolver_is_thread_safe`,
    is included to prove that the lazy initialization of the default resolver
    is safe from race conditions. This is a critical test for a library
    intended for use in production server environments. It patches the
    `InMemoryResolver` to count how many times its expensive constructor is
    called, asserting it is only ever `1` even when accessed by many threads
    concurrently.
"""
import pytest
import threading
from unittest.mock import MagicMock, patch

from geofence_validator import errors, core
from geofence_validator.core import Validator, is_ip_allowed

# A standard set of countries for use across multiple tests.
POLICY_COUNTRIES = {"US", "CA"}


# ==============================================================================
# Mock Resolver for Controlled Unit Testing
# ==============================================================================

@pytest.fixture
def mock_resolver() -> MagicMock:
    """
    A pytest fixture that provides a mock of the Resolver class.
    We can dynamically configure its `resolve` method's return value or side effect.
    """
    resolver = MagicMock(spec=core.resolver.Resolver)
    return resolver


# ==============================================================================
# Tests for the Validator Class (High-Performance API)
# ==============================================================================

class TestValidator:
    """Test suite for the core `Validator` class."""

    def test_init_success(self, mock_resolver: MagicMock):
        """Verify the Validator initializes correctly with a custom resolver."""
        validator = Validator(
            "whitelist", POLICY_COUNTRIES, custom_resolver=mock_resolver
        )
        assert validator.policy is not None
        assert validator.resolver is mock_resolver

    # --- Whitelist Scenarios ---
    def test_check_whitelist_allowed(self, mock_resolver: MagicMock):
        """Test a successful 'allow' case with a whitelist policy."""
        mock_resolver.resolve.return_value = "US"
        validator = Validator(
            "whitelist", POLICY_COUNTRIES, custom_resolver=mock_resolver
        )
        assert validator.check("1.2.3.4") is True
        mock_resolver.resolve.assert_called_once_with("1.2.3.4")

    def test_check_whitelist_denied(self, mock_resolver: MagicMock):
        """Test a successful 'deny' case with a whitelist policy."""
        mock_resolver.resolve.return_value = "DE"
        validator = Validator(
            "whitelist", POLICY_COUNTRIES, custom_resolver=mock_resolver
        )
        assert validator.check("5.6.7.8") is False
        mock_resolver.resolve.assert_called_once_with("5.6.7.8")

    def test_check_whitelist_unknown_ip_is_denied(self, mock_resolver: MagicMock):
        """Test that an IP not found by the resolver is denied by a whitelist."""
        mock_resolver.resolve.side_effect = errors.IPAddressNotFoundError("9.9.9.9")
        validator = Validator(
            "whitelist", POLICY_COUNTRIES, custom_resolver=mock_resolver
        )
        assert validator.check("9.9.9.9") is False

    # --- Blacklist Scenarios ---
    def test_check_blacklist_denied(self, mock_resolver: MagicMock):
        """Test a successful 'deny' case with a blacklist policy."""
        mock_resolver.resolve.return_value = "US"
        validator = Validator(
            "blacklist", POLICY_COUNTRIES, custom_resolver=mock_resolver
        )
        assert validator.check("1.2.3.4") is False

    def test_check_blacklist_allowed(self, mock_resolver: MagicMock):
        """Test a successful 'allow' case with a blacklist policy."""
        mock_resolver.resolve.return_value = "DE"
        validator = Validator(
            "blacklist", POLICY_COUNTRIES, custom_resolver=mock_resolver
        )
        assert validator.check("5.6.7.8") is True

    def test_check_blacklist_unknown_ip_is_allowed(self, mock_resolver: MagicMock):
        """Test that an IP not found by the resolver is allowed by a blacklist."""
        mock_resolver.resolve.side_effect = errors.IPAddressNotFoundError("9.9.9.9")
        validator = Validator(
            "blacklist", POLICY_COUNTRIES, custom_resolver=mock_resolver
        )
        assert validator.check("9.9.9.9") is True

    # --- Error Propagation ---
    @pytest.mark.parametrize(
        "error_to_raise",
        [
            errors.InvalidIPAddressError("bad-ip"),
            errors.NonPublicIPAddressError("127.0.0.1", "loopback"),
        ],
    )
    def test_check_propagates_validation_errors(
        self, mock_resolver: MagicMock, error_to_raise: errors.ValidationError
    ):
        """
        Verify that validation errors from the resolver are re-raised by `check`.
        """
        mock_resolver.resolve.side_effect = error_to_raise
        validator = Validator(
            "whitelist", POLICY_COUNTRIES, custom_resolver=mock_resolver
        )
        with pytest.raises(type(error_to_raise)):
            validator.check("some-ip")


# ==============================================================================
# Tests for the Functional Wrapper (Convenience API)
# ==============================================================================

class TestIsIpAllowed:
    """Test suite for the `is_ip_allowed` functional wrapper."""

    def test_functional_wrapper_works(self, mock_resolver: MagicMock):
        """
        Verify the functional wrapper delegates correctly to the Validator class.
        """
        mock_resolver.resolve.return_value = "CA"
        result = is_ip_allowed(
            "1.2.3.4", "whitelist", POLICY_COUNTRIES, custom_resolver=mock_resolver
        )
        assert result is True
        mock_resolver.resolve.assert_called_once_with("1.2.3.4")


# ==============================================================================
# Tests for Concurrency and State Management
# ==============================================================================

class TestStateAndConcurrency:
    """Tests for singleton creation and thread safety."""

    def test_default_resolver_is_thread_safe(self, monkeypatch):
        """
        CRITICAL: Verify that `_get_default_resolver` is thread-safe and only
        initializes the expensive `InMemoryResolver` once, even when called
        concurrently from multiple threads.
        """
        # Ensure the global resolver is reset for this test
        monkeypatch.setattr(core, "_DEFAULT_RESOLVER", None)

        # Patch the actual InMemoryResolver to spy on its constructor
        mock_init = MagicMock()
        
        # We need to mock the original __init__ to track calls, but also
        # call the real init so it doesn't break. Here, we can just assign
        # a mock that doesn't do anything because we won't actually resolve.
        mock_resolver_instance = MagicMock()
        mock_init.return_value = mock_resolver_instance
        
        # We need to patch the class in the 'core' module where it's imported and used.
        with patch('geofence_validator.core.resolver.InMemoryResolver', mock_init):
            
            num_threads = 20
            barrier = threading.Barrier(num_threads)
            threads = []

            def target():
                """Function to be run by each thread."""
                barrier.wait()  # Synchronize threads to start at the same time
                core._get_default_resolver()

            for _ in range(num_threads):
                thread = threading.Thread(target=target)
                threads.append(thread)
                thread.start()

            for thread in threads:
                thread.join()

            # The ultimate assertion: was the expensive constructor called only once?
            assert mock_init.call_count == 1