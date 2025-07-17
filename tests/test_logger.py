import logging
import sys
import types
import pytest
import builtins

import geofence_validator.logger as logger_mod

def get_library_logger():
    return logging.getLogger(logger_mod.LIBRARY_LOGGER_NAME)

def clear_library_logger_handlers():
    lib_logger = get_library_logger()
    for handler in lib_logger.handlers[:]:
        lib_logger.removeHandler(handler)
    lib_logger.setLevel(logging.NOTSET)
    lib_logger.propagate = True

def test_setup_library_logging_adds_nullhandler(monkeypatch):
    clear_library_logger_handlers()
    # Now call the setup function
    logger_mod.setup_library_logging()
    lib_logger = get_library_logger()
    # It should have one handler that is a NullHandler
    assert len(lib_logger.handlers) == 1
    assert isinstance(lib_logger.handlers[0], logging.NullHandler)
    assert lib_logger.propagate is False

def test_setup_library_logging_does_not_duplicate_handlers():
    clear_library_logger_handlers()
    lib_logger = get_library_logger()
    lib_logger.addHandler(logging.NullHandler())
    handler_count = len(lib_logger.handlers)
    logger_mod.setup_library_logging()
    assert len(lib_logger.handlers) == handler_count  # No duplicate handlers

def test_enable_debugging_without_rich(monkeypatch):
    clear_library_logger_handlers()
    # Simulate ImportError for rich
    monkeypatch.setitem(sys.modules, "rich.logging", None)
    def fake_import(name, *args, **kwargs):
        if name == "rich.logging":
            raise ImportError
        return __import__(name, *args, **kwargs)
    monkeypatch.setattr("builtins.__import__", fake_import)
    logger_mod.enable_debugging(logging.INFO)
    lib_logger = get_library_logger()
    assert lib_logger.level == logging.INFO
    assert lib_logger.propagate is False
    assert any(isinstance(h, logging.StreamHandler) for h in lib_logger.handlers)
    # Should not have RichHandler
    assert not any(h.__class__.__name__ == "RichHandler" for h in lib_logger.handlers)

def test_enable_debugging_with_rich(monkeypatch):
    clear_library_logger_handlers()
    # Fake RichHandler
    class DummyRichHandler(logging.Handler):
        def __init__(self, **kwargs):
            super().__init__()
            self.kwargs = kwargs

        def emit(self, record):
            pass   # Do nothing to avoid the error
    dummy_module = types.SimpleNamespace(RichHandler=DummyRichHandler)
    monkeypatch.setitem(sys.modules, "rich.logging", dummy_module)
    logger_mod.enable_debugging(logging.DEBUG)
    lib_logger = get_library_logger()
    assert lib_logger.level == logging.DEBUG
    assert lib_logger.propagate is False
    assert any(isinstance(h, DummyRichHandler) for h in lib_logger.handlers)

def test_enable_debugging_clears_existing_handlers():
    clear_library_logger_handlers()
    lib_logger = get_library_logger()
    dummy_handler = logging.StreamHandler()
    lib_logger.addHandler(dummy_handler)
    assert dummy_handler in lib_logger.handlers
    # Simulate ImportError for rich
    orig_import = __import__
    def fake_import(name, *args, **kwargs):
        if name == "rich.logging":
            raise ImportError
        return orig_import(name, *args, **kwargs)
    builtins.__import__, orig = fake_import, builtins.__import__
    try:
        logger_mod.enable_debugging(logging.WARNING)
    finally:
        builtins.__import__ = orig
    assert dummy_handler not in lib_logger.handlers
    assert any(isinstance(h, logging.StreamHandler) for h in lib_logger.handlers)