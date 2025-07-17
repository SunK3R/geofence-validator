# -*- coding: utf-8 -*-
"""
test_policy.py - Unit Tests for the Geofence Policy Logic.

This test suite exhaustively covers the behavior of the policy module, ensuring
that the core logic of the library is sound, predictable, and correct.

The tests are structured into classes for each major component being tested:
- `TestWhitelistPolicy`: Verifies all logical paths for the whitelist rule.
- `TestBlacklistPolicy`: Verifies all logical paths for the blacklist rule.
- `TestPolicyFactory`: Verifies the `get_policy` factory function, including
  its validation of rule names and policy definitions.

We use `pytest.mark.parametrize` extensively to test a wide range of scenarios
(different countries, `None` values) with concise, readable code. This approach
ensures that we are not just testing the "happy path," but are explicitly
verifying every documented edge case.
"""
import pytest
from typing import Optional, Set

from geofence_validator.errors import (
    InvalidPolicyDefinitionError,
    InvalidPolicyRuleError,
)
from geofence_validator.policy import (
    BlacklistPolicy,
    WhitelistPolicy,
    get_policy,
)

# ==============================================================================
# Constants and Fixtures
# ==============================================================================

# A standard set of countries for use across multiple tests.
POLICY_COUNTRIES: Set[str] = {"US", "CA", "GB"}


# ==============================================================================
# Test Cases for WhitelistPolicy
# ==============================================================================

class TestWhitelistPolicy:
    """Test suite for the WhitelistPolicy logic."""

    @pytest.fixture(scope="class")
    def policy(self) -> WhitelistPolicy:
        """A reusable WhitelistPolicy instance for this test class."""
        return WhitelistPolicy(countries=frozenset(POLICY_COUNTRIES))

    @pytest.mark.parametrize(
        "resolved_country, expected",
        [
            ("US", True),  # Country is in the whitelist
            ("CA", True),  # Country is in the whitelist
            ("DE", False), # Country is not in the whitelist
            ("JP", False), # Country is not in the whitelist
        ],
    )
    def test_known_countries(
        self, policy: WhitelistPolicy, resolved_country: str, expected: bool
    ):
        """
        Verify that known countries are correctly allowed or denied based on
        their presence in the whitelist.
        """
        assert policy.is_allowed(resolved_country) is expected

    def test_unresolved_country_is_denied(self, policy: WhitelistPolicy):
        """
        CRITICAL: Verify that an unresolved country (None) is ALWAYS denied
        by a whitelist policy.
        """
        assert policy.is_allowed(None) is False

    def test_country_case_sensitivity(self, policy: WhitelistPolicy):
        """
        Verify that lookups are case-sensitive. 'us' should not match 'US'.
        This confirms the underlying set logic is behaving as expected.
        """
        assert policy.is_allowed("us") is False

    def test_policy_is_immutable(self, policy: WhitelistPolicy):
        """
        Verify that the policy is a frozen dataclass and cannot be modified
        at runtime, which is a key compliance feature.
        """
        with pytest.raises(AttributeError):
            # The exact error can be `dataclasses.FrozenInstanceError` in Python 3.7+
            # but checking for AttributeError is a safe, compatible way.
            policy.countries = frozenset({"FR"})  # type: ignore


# ==============================================================================
# Test Cases for BlacklistPolicy
# ==============================================================================

class TestBlacklistPolicy:
    """Test suite for the BlacklistPolicy logic."""

    @pytest.fixture(scope="class")
    def policy(self) -> BlacklistPolicy:
        """A reusable BlacklistPolicy instance for this test class."""
        return BlacklistPolicy(countries=frozenset(POLICY_COUNTRIES))

    @pytest.mark.parametrize(
        "resolved_country, expected",
        [
            ("US", False), # Country is in the blacklist
            ("CA", False), # Country is in the blacklist
            ("DE", True),  # Country is not in the blacklist
            ("JP", True),  # Country is not in the blacklist
        ],
    )
    def test_known_countries(
        self, policy: BlacklistPolicy, resolved_country: str, expected: bool
    ):
        """
        Verify that known countries are correctly allowed or denied based on
        their presence in the blacklist.
        """
        assert policy.is_allowed(resolved_country) is expected

    def test_unresolved_country_is_allowed(self, policy: BlacklistPolicy):
        """
        CRITICAL: Verify that an unresolved country (None) is ALWAYS allowed
        by a blacklist policy.
        """
        assert policy.is_allowed(None) is True

    def test_country_case_sensitivity(self, policy: BlacklistPolicy):
        """
        Verify that lookups are case-sensitive. 'us' should not match 'US'.
        """
        assert policy.is_allowed("us") is True


# ==============================================================================
# Test Cases for the Policy Factory (`get_policy`)
# ==============================================================================

class TestPolicyFactory:
    """Test suite for the get_policy factory function."""

    @pytest.mark.parametrize(
        "rule_name, expected_class",
        [
            ("whitelist", WhitelistPolicy),
            ("blacklist", BlacklistPolicy),
            ("WHITELIST", WhitelistPolicy), # Test case insensitivity
            ("BlackList", BlacklistPolicy), # Test case insensitivity
        ],
    )
    def test_valid_policy_creation(
        self, rule_name: str, expected_class: type
    ):
        """
        Verify that the factory returns the correct policy class instance
        for all valid (and case-insensitive) rule names.
        """
        policy = get_policy(rule_name, POLICY_COUNTRIES)
        assert isinstance(policy, expected_class)
        assert policy.countries == frozenset(POLICY_COUNTRIES)

    def test_get_policy_raises_on_invalid_rule(self):
        """
        Verify that the factory raises an InvalidPolicyRuleError for an
        unsupported rule name.
        """
        with pytest.raises(InvalidPolicyRuleError) as exc_info:
            get_policy("allow_only", POLICY_COUNTRIES)

        # Check that the exception object contains useful context
        assert exc_info.value.unsupported_rule == "allow_only"
        assert "whitelist" in exc_info.value.supported_rules
        assert "blacklist" in exc_info.value.supported_rules
        assert "not supported" in str(exc_info.value)

    @pytest.mark.parametrize("rule_name", ["whitelist", "blacklist"])
    def test_get_policy_raises_on_empty_countries(self, rule_name: str):
        """
        Verify that creating any policy with an empty set of countries raises
        an InvalidPolicyDefinitionError, as this is a meaningless policy.
        """
        with pytest.raises(InvalidPolicyDefinitionError) as exc_info:
            get_policy(rule_name, set())

        assert "cannot be created with an empty set of countries" in str(
            exc_info.value
        )