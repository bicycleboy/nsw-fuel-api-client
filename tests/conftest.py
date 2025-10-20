import re
import pytest
import aiohttp
from aioresponses import aioresponses

from nsw_fuel.const import AUTH_URL


@pytest.fixture
async def session():
    """Function-scoped aiohttp session for each test."""
    async with aiohttp.ClientSession() as sess:
        yield sess

@pytest.fixture
def mock_token():
    """
    Fixture to mock the FuelCheck API token endpoint.
    Returns an aioresponses context manager.
    """
    with aioresponses() as m:
        token_resp = {"access_token": "testtoken", "expires_in": 3600}
        # aioresponses supports regex matching for URLs; AUTH_URL might be called with params
        m.get(re.compile(re.escape(AUTH_URL)), payload=token_resp)
        yield m
