# -*- coding: utf-8 -*-
"""
test_main.py - Unit Tests for the Command-Line Interface.

This suite tests the `__main__` module, which serves as the executable
entry point for the library.

Testing Strategy:
-   **Direct Function Calls**: We import the `main` function from the module
    and call it directly with a list of simulated command-line arguments. This
    is far more efficient and robust than using `subprocess`.
-   **Mocking Core Logic**: We use `unittest.mock.patch` to replace the
    `Validator` class within the `__main__` module's namespace. This completely
    isolates the CLI's logic (argument parsing, output handling, exit codes)
    from the actual geofencing logic, which is already tested elsewhere.
-   **Capturing Output**: The `capsys` fixture from pytest is used to capture
    and inspect everything written to `stdout` and `stderr`.
-   **Verifying Exit Codes**: We check the integer return value of the `main`
    function to ensure it returns the documented exit codes (0 for allowed,
    1 for denied, 2 for error).
"""
import pytest
from unittest.mock import MagicMock, patch

from geofence_validator import errors
from geofence_validator.__main__ import main

# ==============================================================================
# Tests for Successful CLI Execution Paths
# ==============================================================================

@patch("geofence_validator.__main__.Validator")
def test_cli_returns_0_on_allowed(mock_validator_class, capsys):
    """
    Verify the CLI prints 'ALLOWED' to stdout and returns exit code 0
    when the validator's check passes.
    """
    # Configure the mock instance that will be created
    mock_instance = mock_validator_class.return_value
    mock_instance.check.return_value = True

    argv = ["8.8.8.8", "whitelist", "US", "CA"]
    return_code = main(argv)

    assert return_code == 0
    captured = capsys.readouterr()
    assert "ALLOWED" in captured.out
    assert captured.err == ""
    mock_instance.check.assert_called_once_with("8.8.8.8")


@patch("geofence_validator.__main__.Validator")
def test_cli_returns_1_on_denied(mock_validator_class, capsys):
    """
    Verify the CLI prints 'DENIED' to stdout and returns exit code 1
    when the validator's check fails.
    """
    mock_instance = mock_validator_class.return_value
    mock_instance.check.return_value = False

    argv = ["1.2.3.4", "blacklist", "US"]
    return_code = main(argv)

    assert return_code == 1
    captured = capsys.readouterr()
    assert "DENIED" in captured.out
    assert captured.err == ""
    mock_instance.check.assert_called_once_with("1.2.3.4")


# ==============================================================================
# Tests for CLI Error Handling and Argument Parsing
# ==============================================================================

@pytest.mark.parametrize(
    "error_to_raise, expected_message_part",
    [
        (errors.InvalidIPAddressError("bad-ip"), "not a valid"),
        (errors.NonPublicIPAddressError("127.0.0.1", "loopback"), "non-public"),
        (errors.IPAddressNotFoundError("9.9.9.9"), "not found"),
        (errors.ResolverInitializationError("File is bad"), "Failed to initialize"),
        (errors.InvalidPolicyRuleError("maybe", ("a", "b")), "not supported"),
    ],
)
@patch("geofence_validator.__main__.Validator")
def test_cli_handles_known_errors_gracefully(
    mock_validator_class,
    capsys,
    error_to_raise: errors.GeofenceError,
    expected_message_part: str,
):
    """
    Verify the CLI catches all expected GeofenceError subclasses, prints a
    user-friendly message to stderr, and returns exit code 2.
    """
    # Configure the mock to raise the specified error when `check` is called
    mock_instance = mock_validator_class.return_value
    mock_instance.check.side_effect = error_to_raise

    argv = ["8.8.8.8", "whitelist", "US"]
    return_code = main(argv)

    assert return_code == 2
    captured = capsys.readouterr()
    assert captured.out == ""  # No output to stdout on error
    assert "Error:" in captured.err
    assert expected_message_part in captured.err


@patch("geofence_validator.__main__.Validator")
def test_cli_handles_unexpected_errors(mock_validator_class, capsys):
    """
    Verify the CLI has a general catch-all for unexpected exceptions and
    returns exit code 2.
    """
    mock_instance = mock_validator_class.return_value
    mock_instance.check.side_effect = ValueError("Something completely unexpected.")

    argv = ["8.8.8.8", "whitelist", "US"]
    return_code = main(argv)

    assert return_code == 2
    captured = capsys.readouterr()
    assert "An unexpected error occurred" in captured.err


def test_cli_argparse_fails_on_bad_rule(capsys):
    """
    Verify that argparse itself enforces the 'choices' for policy_rule.
    """
    argv = ["8.8.8.8", "badrule", "US"]
    with pytest.raises(SystemExit) as exc_info:
        main(argv)

    # Argparse exits with code 2 for invalid arguments
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "invalid choice: 'badrule'" in captured.err


@patch("geofence_validator.__main__.enable_debugging")
@patch("geofence_validator.__main__.Validator")
def test_cli_verbose_flag_enables_debugging(mock_validator_class, mock_enable_debugging):
    """
    Verify that providing the -v or --verbose flag calls enable_debugging.
    """
    # We don't care about the result of the main call, just that it runs without error.
    # The mock_validator_class ensures no real logic is triggered.
    main(["-v", "8.8.8.8", "whitelist", "US"])

    # The only thing we care about: was our function called?
    mock_enable_debugging.assert_called_once()


@patch("geofence_validator.__main__.InMemoryResolver")
@patch("geofence_validator.__main__.Validator")
def test_cli_data_file_flag_uses_custom_resolver(
    mock_validator_class, mock_resolver_class, capsys
):
    """
    Verify that using --data-file correctly instantiates the InMemoryResolver
    with the specified path and passes it to the Validator.
    """
    mock_validator_instance = mock_validator_class.return_value
    mock_validator_instance.check.return_value = True
    
    data_file_path = "/fake/path/to/data.csv"
    argv = ["--data-file", data_file_path, "8.8.8.8", "whitelist", "US"]
    
    main(argv)

    # Assert that InMemoryResolver was called with the correct path
    mock_resolver_class.assert_called_once_with(data_file_path=data_file_path)
    
    # Assert that Validator was initialized with the instance of our custom resolver
    mock_validator_class.assert_called_once()
    # The 'custom_resolver' kwarg should be the instance returned by our mock resolver class
    assert mock_validator_class.call_args.kwargs['custom_resolver'] is mock_resolver_class.return_value