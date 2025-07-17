# -*- coding: utf-8 -*-
"""
test_resolver.py - Unit Tests for the IP-to-Country Resolver.

This suite provides exhaustive testing for the `InMemoryResolver`, which is a
critical component involving file I/O, data parsing, and IP address logic.

The tests are structured as follows:
1.  **Fixtures**: A `test_data_dir` fixture creates a temporary directory and
    populates it with a variety of test CSV files:
    - A perfectly valid data file.
    - Files with specific errors (bad CIDR, bad format).
    - Files representing edge cases (empty, comments).

2.  **`TestInMemoryResolverInitialization`**: Focuses solely on the `__init__`
    method. It tests that the resolver can be created successfully with valid
    data and that it raises the correct, specific `ResolverInitializationError`
    for every conceivable type of malformed input file.

3.  **`TestInMemoryResolverResolution`**: Assumes a correctly initialized
    resolver. It tests the `resolve` method itself, verifying:
    - Correct resolution of both IPv4 and IPv6 addresses.
    - Correct raising of `IPAddressNotFoundError` for unknown public IPs.
    - Correct raising of `InvalidIPAddressError` for malformed IP strings.
    - Correct raising of `NonPublicIPAddressError` for all categories of
      reserved IP addresses (private, loopback, link-local, etc.).
"""
import pytest
from pathlib import Path

from geofence_validator.errors import (
    IPAddressNotFoundError,
    InvalidIPAddressError,
    NonPublicIPAddressError,
    ResolverInitializationError,
)
from geofence_validator.resolver import InMemoryResolver


# ==============================================================================
# Fixtures for Creating a Controlled Test Environment
# ==============================================================================

@pytest.fixture(scope="module")
def test_data_dir(tmp_path_factory) -> Path:
    """
    Creates a temporary directory and populates it with various test CSV files.
    This fixture is module-scoped for efficiency, as the files are read-only.
    """
    tmp_path = tmp_path_factory.mktemp("resolver_data")

    # 1. A perfectly valid data file
    (tmp_path / "good_data.csv").write_text(
        """
# Sample IP Ranges
8.8.8.0/24,US
1.1.1.1/32,AU
2001:4860:4860::8888/128,US
212.58.224.0/20,GB
"""
    )

    # 2. Data file with an invalid CIDR notation
    (tmp_path / "bad_cidr.csv").write_text("8.8.8.0/33,US\n")

    # 3. Data file with incorrect column count
    (tmp_path / "bad_format.csv").write_text("8.8.8.0/24,US,EXTRA_COLUMN\n")

    # 4. An empty data file
    (tmp_path / "empty.csv").write_text("")

    # 5. Data file with comments and empty lines to test robust parsing
    (tmp_path / "mixed_data.csv").write_text(
        """
# This is a comment
1.0.0.0/24,AU

# Another comment
78.46.0.0/15,DE
"""
    )
    return tmp_path


# ==============================================================================
# Tests for Resolver Initialization
# ==============================================================================

class TestInMemoryResolverInitialization:
    """Tests focused on the constructor logic of InMemoryResolver."""

    def test_init_with_valid_custom_file(self, test_data_dir: Path):
        """Verify successful initialization with a well-formed data file."""
        data_file = test_data_dir / "good_data.csv"
        try:
            resolver = InMemoryResolver(data_file_path=str(data_file))
            # Check that some data was actually loaded
            assert len(resolver._compiled_ranges) == 4
        except ResolverInitializationError:
            pytest.fail("ResolverInitializationError was raised unexpectedly.")

    def test_init_with_comments_and_empty_lines(self, test_data_dir: Path):
        """Verify that comments and blank lines in the data file are ignored."""
        data_file = test_data_dir / "mixed_data.csv"
        resolver = InMemoryResolver(data_file_path=str(data_file))
        assert len(resolver._compiled_ranges) == 2

    def test_init_raises_on_nonexistent_file(self, test_data_dir: Path):
        """Verify an error is raised if the data file path does not exist."""
        non_existent_file = test_data_dir / "no_such_file.csv"
        with pytest.raises(ResolverInitializationError) as exc_info:
            InMemoryResolver(data_file_path=str(non_existent_file))
        assert "Data file not found" in str(exc_info.value)

    def test_init_raises_on_bad_cidr(self, test_data_dir: Path):
        """Verify an error is raised for data with invalid CIDR notation."""
        data_file = test_data_dir / "bad_cidr.csv"
        with pytest.raises(ResolverInitializationError) as exc_info:
            InMemoryResolver(data_file_path=str(data_file))
        assert "Invalid CIDR notation" in str(exc_info.value)

    def test_init_raises_on_bad_format(self, test_data_dir: Path):
        """Verify an error is raised for data with the wrong number of columns."""
        data_file = test_data_dir / "bad_format.csv"
        with pytest.raises(ResolverInitializationError) as exc_info:
            InMemoryResolver(data_file_path=str(data_file))
        assert "Invalid data format" in str(exc_info.value)

    def test_init_raises_on_empty_file(self, test_data_dir: Path):
        """Verify an error is raised if the data file is empty or has no valid ranges."""
        data_file = test_data_dir / "empty.csv"
        with pytest.raises(ResolverInitializationError) as exc_info:
            InMemoryResolver(data_file_path=str(data_file))
        assert "no valid IP ranges were loaded" in str(exc_info.value)


# ==============================================================================
# Tests for Resolver Resolution Logic
# ==============================================================================

class TestInMemoryResolverResolution:
    """Tests focused on the `resolve` method of a working InMemoryResolver."""

    @pytest.fixture(scope="class")
    def resolver(self, test_data_dir: Path) -> InMemoryResolver:
        """Provides a resolver instance initialized with good data for all tests."""
        return InMemoryResolver(data_file_path=str(test_data_dir / "good_data.csv"))

    @pytest.mark.parametrize(
        "ip, expected_country",
        [
            ("8.8.8.8", "US"),  # IPv4 inside a /24
            ("1.1.1.1", "AU"),  # IPv4 exact match on /32
            ("2001:4860:4860::8888", "US"),  # IPv6 exact match
            ("212.58.224.1", "GB"),  # IPv4 at the start of a range
            ("212.58.239.254", "GB"),  # IPv4 at the end of a range
        ],
    )
    def test_resolve_success(
        self, resolver: InMemoryResolver, ip: str, expected_country: str
    ):
        """Verify successful resolution for various valid public IPs."""
        assert resolver.resolve(ip) == expected_country

    def test_resolve_raises_ip_not_found(self, resolver: InMemoryResolver):
        """Verify an error is raised for a public IP not in our data."""
        unknown_public_ip = "99.99.99.99"
        with pytest.raises(IPAddressNotFoundError) as exc_info:
            resolver.resolve(unknown_public_ip)
        assert exc_info.value.ip_address == unknown_public_ip

    @pytest.mark.parametrize(
        "invalid_ip",
        ["not-an-ip", "1.2.3.4.5", "8.8.8", "2001::8888::1", "999.9.9.9"]
    )
    def test_resolve_raises_invalid_ip(
        self, resolver: InMemoryResolver, invalid_ip: str
    ):
        """Verify an error is raised for malformed IP address strings."""
        with pytest.raises(InvalidIPAddressError) as exc_info:
            resolver.resolve(invalid_ip)
        assert exc_info.value.invalid_ip == invalid_ip

    @pytest.mark.parametrize(
        "non_public_ip, reason_part",
        [
            ("192.168.1.1", "private"),  # Private IPv4
            ("10.0.0.50", "private"),      # Private IPv4
            ("172.16.31.5", "private"),    # Private IPv4
            ("fc00::1", "private"),        # Private IPv6 (ULA)
            ("127.0.0.1", "loopback"),     # Loopback IPv4
            ("::1", "loopback"),           # Loopback IPv6
            ("169.254.10.20", "link-local"), # Link-local IPv4
            ("fe80::1", "link-local"),     # Link-local IPv6
            ("0.0.0.0", "unspecified"),    # Unspecified IPv4
        ],
    )
    def test_resolve_raises_non_public_ip(
        self, resolver: InMemoryResolver, non_public_ip: str, reason_part: str
    ):
        """Verify an error is raised for all categories of non-public IPs."""
        with pytest.raises(NonPublicIPAddressError) as exc_info:
            resolver.resolve(non_public_ip)
        assert exc_info.value.ip_address == non_public_ip
        assert reason_part in exc_info.value.reason