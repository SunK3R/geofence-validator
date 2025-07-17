# -*- coding: utf-8 -*-
"""
policy.py - Geofence Policy Logic and Implementations.

This module provides the core components for defining and evaluating geofencing
policies. The design prioritizes clarity, immutability, and strict adherence
to the principle of least surprise, which are critical for any system used in a
compliance or security context.

The core components are:
1.  `Policy (ABC)`: An abstract base class that defines the contract for all
    policy implementations. It guarantees that any policy will have an
    `is_allowed` method.

2.  `PolicyRule (Enum)`: A type-safe enumeration of the supported policy rules,
    preventing the use of arbitrary "magic strings" in the codebase.

3.  `WhitelistPolicy` & `BlacklistPolicy`: Concrete, immutable implementations
    of the `Policy` contract. These are implemented as frozen dataclasses to
    ensure that a policy's configuration cannot be accidentally modified at
    runtime.

4.  `get_policy()`: A factory function that serves as the public entry point
    for creating policy objects from simple string identifiers and a set of
    country codes.

A key design decision is the explicit and strict handling of unresolved IP
addresses (where the resolved country is `None`):
-   **WhitelistPolicy**: If a country is `None`, access is DENIED. The logic is
    "allow ONLY if the location is on the list." An unknown location cannot
    be on the list.
-   **BlacklistPolicy**: If a country is `None`, access is ALLOWED. The logic is
    "deny ONLY if the location is on the list." An unknown location cannot
    be on the blocklist, so access is permitted by default.

This deterministic behavior is crucial for auditable and predictable systems.
"""
from __future__ import annotations

import abc
import dataclasses
from enum import Enum
from typing import Final, Optional, Set, Type

from .errors import InvalidPolicyDefinitionError, InvalidPolicyRuleError

# ==============================================================================
# Constants and Enumerations
# ==============================================================================

class PolicyRule(str, Enum):
    """
    Enumeration of supported policy rule types.

    Using an Enum makes the policy selection type-safe and self-documenting,
    preventing errors from typos or unsupported rule strings.
    """
    WHITELIST = "whitelist"
    BLACKLIST = "blacklist"

    @classmethod
    def supported_rules(cls) -> tuple[str, ...]:
        """Returns a tuple of all supported rule names."""
        return tuple(member.value for member in cls)


# ==============================================================================
# Abstract Base Class for Policies
# ==============================================================================

@dataclasses.dataclass(frozen=True)
class Policy(abc.ABC):
    """
    Abstract base class defining the contract for all geofencing policies.

    This class ensures that any policy implementation will be immutable (`frozen=True`)
    and will provide the necessary methods and properties for evaluation.

    Attributes:
        countries (frozenset[str]): An immutable set of ISO 3166-1 alpha-2
                                    country codes that this policy applies to.
    """
    countries: frozenset[str]

    @property
    @abc.abstractmethod
    def rule(self) -> PolicyRule:
        """The specific rule type implemented by the policy (e.g., WHITELIST)."""
        raise NotImplementedError

    @abc.abstractmethod
    def is_allowed(self, resolved_country: Optional[str]) -> bool:
        """
        Determine if access is permitted based on the resolved country.

        This is the core evaluation method of any policy. It must correctly
        handle cases where the country is known and where it is `None` (i.e.,
        the IP address could not be geolocated).

        Args:
            resolved_country: The two-letter ISO country code resolved from an
                              IP address, or `None` if resolution failed.

        Returns:
            `True` if access is permitted under this policy, `False` otherwise.
        """
        raise NotImplementedError

    def __post_init__(self) -> None:
        """
        Performs validation after the dataclass is initialized.
        Ensures the policy definition is logical.
        """
        if not self.countries:
            raise InvalidPolicyDefinitionError(
                f"A {self.rule.value} policy cannot be created with an empty "
                "set of countries. This would result in a policy that either "
                "blocks all traffic or allows all traffic, rendering it meaningless."
            )


# ==============================================================================
# Concrete Policy Implementations
# ==============================================================================

@dataclasses.dataclass(frozen=True)
class WhitelistPolicy(Policy):
    """
    A policy that allows access ONLY if the location is in the approved set.

    This is a "default-deny" policy. Any country not explicitly listed in the
    `countries` set is denied. Crucially, if the country of origin cannot be
    determined (`resolved_country` is `None`), access is DENIED.
    """
    rule: Final[PolicyRule] = PolicyRule.WHITELIST

    def is_allowed(self, resolved_country: Optional[str]) -> bool:
        """
        Allows access if and only if the resolved country is in the whitelist.

        Args:
            resolved_country: The country code, or `None`.

        Returns:
            `True` only if `resolved_country` is a non-None value present
            in the `countries` set. Returns `False` otherwise.
        """
        if resolved_country is None:
            return False  # Cannot be on the whitelist if location is unknown
        return resolved_country in self.countries


@dataclasses.dataclass(frozen=True)
class BlacklistPolicy(Policy):
    """
    A policy that denies access IF the location is in the forbidden set.

    This is a "default-allow" policy. Any country not explicitly listed in the
    `countries` set is allowed. Crucially, if the country of origin cannot be
    determined (`resolved_country` is `None`), access is ALLOWED.
    """
    rule: Final[PolicyRule] = PolicyRule.BLACKLIST

    def is_allowed(self, resolved_country: Optional[str]) -> bool:
        """
        Denies access if the resolved country is in the blacklist.

        Args:
            resolved_country: The country code, or `None`.

        Returns:
            `False` if `resolved_country` is present in the `countries` set.
            Returns `True` otherwise (including when `resolved_country` is `None`).
        """
        if resolved_country is None:
            return True  # Cannot be on the blacklist if location is unknown
        return resolved_country not in self.countries


# ==============================================================================
# Policy Factory
# ==============================================================================

_POLICY_IMPLEMENTATIONS: Final[dict[PolicyRule, Type[Policy]]] = {
    PolicyRule.WHITELIST: WhitelistPolicy,
    PolicyRule.BLACKLIST: BlacklistPolicy,
}


def get_policy(rule_name: str, countries: Set[str]) -> Policy:
    """
    Factory function to create a Policy object from its string name.

    This is the primary way for external code to construct a policy object,
    abstracting away the specific implementation classes.

    Args:
        rule_name: The name of the rule, e.g., "whitelist" or "blacklist".
        countries: A set of two-letter ISO country codes to apply to the policy.

    Returns:
        An immutable, configured instance of a `Policy` subclass.

    Raises:
        InvalidPolicyRuleError: If the `rule_name` is not a supported policy.
        InvalidPolicyDefinitionError: If the policy is defined with invalid
                                      parameters (e.g., an empty country set).
    """
    try:
        policy_rule = PolicyRule(rule_name.lower())
    except ValueError:
        raise InvalidPolicyRuleError(
            unsupported_rule=rule_name,
            supported_rules=PolicyRule.supported_rules(),
        )

    policy_class = _POLICY_IMPLEMENTATIONS[policy_rule]
    
    # The concrete class will perform its own validation in __post_init__.
    return policy_class(countries=frozenset(countries))