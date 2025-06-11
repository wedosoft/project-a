import importlib
import os
import sys
import types

import pytest

REQUIRED_ENV_VARS = [
    "FRESHDESK_DOMAIN",
    "FRESHDESK_API_KEY",
    "QDRANT_URL",
    "QDRANT_API_KEY",
    "OPENAI_API_KEY",
]

DEFAULTS = {
    "FRESHDESK_DOMAIN": "example.freshdesk.com",
    "FRESHDESK_API_KEY": "dummy",
    "QDRANT_URL": ":memory:",
    "QDRANT_API_KEY": "dummy",
    "OPENAI_API_KEY": "dummy",
    "COMPANY_ID": "development-default",
}

try:
    importlib.import_module("google.generativeai")
    _GEN_AI_MISSING = False
except Exception:
    _GEN_AI_MISSING = True
    # stub modules to avoid import errors during collection
    google_stub = types.ModuleType("google")
    genai_stub = types.ModuleType("google.generativeai")
    sys.modules.setdefault("google", google_stub)
    sys.modules.setdefault("google.generativeai", genai_stub)

try:
    importlib.import_module("cachetools")
except Exception:
    cachetools_stub = types.ModuleType("cachetools")
    cachetools_stub.TTLCache = lambda *args, **kwargs: None
    sys.modules.setdefault("cachetools", cachetools_stub)


_SKIP_REASON = None


def pytest_configure(config):
    global _SKIP_REASON
    for key, value in DEFAULTS.items():
        os.environ.setdefault(key, value)
    missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    reason_parts = []
    if missing:
        reason_parts.append("Missing environment variables: " + ", ".join(missing))
    if _GEN_AI_MISSING:
        reason_parts.append("google-generativeai package not installed")
    if reason_parts:
        _SKIP_REASON = "; ".join(reason_parts)


def pytest_collection_modifyitems(config, items):
    if _SKIP_REASON:
        skip_marker = pytest.mark.skip(reason=_SKIP_REASON)
        for item in items:
            item.add_marker(skip_marker)
