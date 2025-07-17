# -*- coding: utf-8 -*-
"""
core.py - The main engine and user-facing API for the geofence-validator.

This module provides the `Validator` class, which is the high-performance,
reusable engine for all geofencing operations. It is designed to be
instantiated once with a specific policy and then used repeatedly to check
numerous IP addresses, amortizing the initial setup cost.

For convenience, a simple functional wrapper, `is_ip_allowed`, is also provided
for one-off checks.

**Design Philosophy**

1.  **Object-Oriented Core (`Validator` class)**: Encapsulates the complete
    validation context (resolver and policy). This makes state explicit and
    avoids re-creating policy objects on every call, leading to significant
    performance gains in real-world applications.

2.  **Thread-Safe Lazy Initialization**: The default `InMemoryResolver`, which is
    expensive to create due to file I/O and parsing, is initialized only once
    when first needed. The initialization is protected by a `threading.Lock`
    to ensure it is safe to use in multi-threaded environments without race
    conditions.

3.  **Facade for Simplicity (`is_ip_allowed` function)**: Retains a simple,
    procedural entry point for users who only need to perform a single check.
    This function is a thin wrapper around the `Validator` class.

This combination of a powerful, reusable class and a simple functional facade
provides both performance for power users and ease of use for simple cases.
"""
from __future__ import annotations

import logging
import threading
from typing import ClassVar, Optional, Set

from . import errors, policy, resolver
from .logger import setup_library_logging

# Set up the library's logger on first import (silent by default).
setup_library_logging()
_log = logging.getLogger(__name__)

# ==============================================================================
# Thread-Safe Singleton Pattern for Default Resolver
# ==============================================================================

# A class-level cache for the default resolver instance.
_DEFAULT_RESOLVER: ClassVar[Optional[resolver.Resolver]] = None
# A lock to ensure thread-safe lazy initialization of the expensive resolver.
_RESOLVER_INIT_LOCK: ClassVar[threading.Lock] = threading.Lock()


def _get_default_resolver() -> resolver.Resolver:
    """
    Lazily initializes and returns a singleton instance of the InMemoryResolver.

    This function is thread-safe. The first thread to enter will initialize the
    resolver, and subsequent threads will wait on the lock until it's ready,
    after which they will immediately receive the cached instance.
    """
    global _DEFAULT_RESOLVER
    # Fast path: check without acquiring the lock first.
    if _DEFAULT_RESOLVER is not None:
        return _DEFAULT_RESOLVER

    with _RESOLVER_INIT_LOCK:
        # Second check: another thread might have initialized it while we waited.
        if _DEFAULT_RESOLVER is None:
            _log.info(
                "First run: initializing default InMemoryResolver (thread-safe)..."
            )
            try:
                _DEFAULT_RESOLVER = resolver.InMemoryResolver(internal_logger=_log)
            except errors.ResolverInitializationError as e:
                _log.critical(
                    "Failed to initialize default resolver. The library is unusable "
                    "without a valid data source. Details: %s",
                    e,
                    exc_info=True,
                )
                raise e
    
    # The type checker can't infer that _DEFAULT_RESOLVER is now non-None.
    return _DEFAULT_RESOLVER  # type: ignore


# ==============================================================================
# The Core Validator Class
# ==============================================================================

class Validator:
    """
    A reusable geofence validation engine.

    This class is the recommended way to use the library for any application that
    performs more than one check. It pre-compiles the policy and resolver,
    making subsequent checks on IP addresses extremely fast.

    Usage:
        >>> from geofence_validator import Validator
        >>> us_ca_whitelist = Validator(policy_rule="whitelist", countries={"US", "CA"})
        >>>
        >>> # Now, use this instance repeatedly
        >>> us_ca_whitelist.check("8.8.8.8")
        True
        >>> us_ca_whitelist.check("78.46.10.20")
        False
    """

    def __init__(
        self,
        policy_rule: str,
        countries: Set[str],
        *,
        custom_resolver: Optional[resolver.Resolver] = None,
    ):
        """
        Initializes the Validator with a specific policy and resolver.

        Args:
            policy_rule: The rule to apply ("whitelist" or "blacklist").
            countries: A set of two-letter, uppercase ISO 3166-1 alpha-2 country
                       codes to use in the policy.
            custom_resolver: (Keyword-only) An optional, pre-initialized resolver
                             instance. If None, the default `InMemoryResolver`
                             is used.

        Raises:
            InvalidPolicyRuleError: If `policy_rule` is not a supported rule.
            InvalidPolicyDefinitionError: If the policy is configured illogically.
            ResolverInitializationError: If the default resolver cannot be created.
        """
        self._resolver = custom_resolver or _get_default_resolver()
        self._policy = policy.get_policy(policy_rule, countries)
        
        _log.info(
            "Validator instance created: rule='%s', countries=%d, resolver='%s'",
            self._policy.rule.value,
            len(self._policy.countries),
            type(self._resolver).__name__,
        )

    @property
    def policy(self) -> policy.Policy:
        """The configured policy object for this validator instance."""
        return self._policy

    @property
    def resolver(self) -> resolver.Resolver:
        """The configured resolver for this validator instance."""
        return self._resolver

    def check(self, ip_address: str) -> bool:
        """
        Performs a geofence check for the given IP address using the configured policy.

        Args:
            ip_address: The IPv4 or IPv6 address string to validate.

        Returns:
            `True` if the IP is allowed, `False` otherwise.

        Raises:
            InvalidIPAddressError: If `ip_address` is not a valid IP string.
            NonPublicIPAddressError: If `ip_address` is a private, loopback, or
                                     otherwise unresolvable address.
        """
        _log.debug("Checking IP '%s' with configured validator...", ip_address)
        resolved_country: Optional[str] = None
        try:
            resolved_country = self._resolver.resolve(ip_address)
            _log.debug(
                "Resolved IP '%s' to country '%s'", ip_address, resolved_country
            )
        except errors.IPAddressNotFoundError:
            _log.warning(
                "IP '%s' is public but not in database. Evaluating as 'Unknown'.",
                ip_address,
            )
            resolved_country = None
        except errors.ValidationError as e:
            _log.warning("Input validation failed for IP '%s': %s", ip_address, e)
            raise

        is_allowed = self._policy.is_allowed(resolved_country)
        _log.info(
            "Decision for IP '%s' (Country: %s): %s",
            ip_address,
            resolved_country or "Unknown",
            "[bold green]ALLOWED[/bold green]" if is_allowed else "[bold red]DENIED[/bold red]",
            extra={"markup": True}
        )
        return is_allowed

    def __repr__(self) -> str:
        return (
            f"Validator(policy_rule='{self._policy.rule.value}', "
            f"countries={len(self._policy.countries)})"
        )


# ==============================================================================
# Convenient Functional Wrapper
# ==============================================================================

def is_ip_allowed(
    ip_address: str,
    policy_rule: str,
    countries: Set[str],
    *,
    custom_resolver: Optional[resolver.Resolver] = None,
) -> bool:
    """
    Performs a single, one-off geofence validation for a given IP address.

    This function is a convenient wrapper around the `Validator` class. For
    applications performing many checks, it is more performant to create a
    single `Validator` instance and reuse its `check()` method.

    Args:
        ip_address: The IPv4 or IPv6 address string to validate.
        policy_rule: The rule to apply ("whitelist" or "blacklist").
        countries: A set of two-letter, uppercase ISO country codes.
        custom_resolver: (Keyword-only) An optional resolver instance.

    Returns:
        `True` if the IP address is allowed, `False` otherwise.
    """
    _log.debug("Using functional wrapper 'is_ip_allowed' for one-off check.")
    validator = Validator(
        policy_rule, countries, custom_resolver=custom_resolver
    )
    return validator.check(ip_address)