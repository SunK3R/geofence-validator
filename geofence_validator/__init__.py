# -*- coding: utf-8 -*-
"""
geofence-validator: A zero-dependency, deterministic library for geofencing.

This __init__.py file serves as the public API for the geofence-validator
package. It explicitly exposes the primary user-facing components, providing a
clean and stable interface for developers.

By importing selected classes and functions here, we allow users to access them
directly from the top-level package, like so:

    from geofence_validator import Validator, is_ip_allowed
    from geofence_validator.errors import GeofenceError

This is more convenient than requiring them to know the internal module
structure (e.g., `from geofence_validator.core import Validator`).

The file also defines the package's version in a single, authoritative location.
"""
from __future__ import annotations

# ==============================================================================
#  Version Information
#  PEP 440: https://www.python.org/dev/peps/pep-0440/
# ==============================================================================
# This is the single source of truth for the package version.
# It is read by packaging tools and can be accessed programmatically.
__version__: str = "0.1.0"


# ==============================================================================
#  Public API Surface
# ==============================================================================
# Import the main user-facing classes and functions from the core module.
# This makes them directly accessible from the 'geofence_validator' namespace.
from .core import Validator, is_ip_allowed

# Import the convenience function for enabling debug logging.
from .logger import enable_debugging

# The `errors` module is not imported directly into the top-level namespace.
# However, this statement makes it possible for users to do:
#   from geofence_validator import errors
#   try:
#       ...
#   except errors.InvalidIPAddressError:
#       ...
# This is a common and clean pattern for exposing exception hierarchies.
from . import errors

# Import the abstract `Resolver` class for users who wish to implement
# their own custom IP resolution logic. We also expose the concrete

# `InMemoryResolver` for those who might want to instantiate it directly
# with a custom data file.
from .resolver import InMemoryResolver, Resolver


# ==============================================================================
#  __all__ Declaration
# ==============================================================================
# Explicitly declare what is considered the "public" API when a user does
# `from geofence_validator import *`.
# While `import *` is generally discouraged, defining `__all__` is a best
# practice for any library that wants to have a well-defined public API.
# It also helps static analysis tools and IDEs understand the package structure.

__all__: list[str] = [
    # Core functionality
    "Validator",
    "is_ip_allowed",

    # Public-facing types and classes
    "Resolver",
    "InMemoryResolver",

    # Custom error module
    "errors",

    # Helper functions
    "enable_debugging",

    # Package version
    "__version__",
]