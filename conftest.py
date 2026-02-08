"""
Root conftest for pytest-django.
Shared fixtures available to all test modules.
"""

import pytest


@pytest.fixture
def api_client(client):
    """Django test client with default headers for HTMX."""
    return client

