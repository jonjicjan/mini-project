import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def synchronous_browser_database_access():
    """Playwright sync runs an event loop in this test thread.

    ORM fixtures are sequential; the live server uses its own thread/connection.
    Limit this exception to browser test sessions, never application settings.
    """
    previous = os.environ.get("DJANGO_ALLOW_ASYNC_UNSAFE")
    os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
    yield
    if previous is None:
        os.environ.pop("DJANGO_ALLOW_ASYNC_UNSAFE", None)
    else:
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = previous
