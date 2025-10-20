# tests/test_integration.py

import pytest
import asyncio
from datetime import datetime, timedelta, timezone

from nsw_fuel import FuelCheckClient


@pytest.fixture
async def session():
    """Provide a fresh aiohttp ClientSession for each test."""
    import aiohttp
    async with aiohttp.ClientSession() as sess:
        yield sess


@pytest.fixture
def client(session):
    """Return a FuelCheckClient instance for integration tests."""
    # Replace with your actual client_id and client_secret
    CLIENT_ID = "YOUR_CLIENT_ID"
    CLIENT_SECRET = "YOUR_CLIENT_SECRET"
    return FuelCheckClient(session=session, client_id=CLIENT_ID, client_secret=CLIENT_SECRET)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_reference_data(client):
    """Integration test for fetching reference data from the real API."""
    # Fetch all reference data
    response = await client.get_reference_data()
    assert len(response.stations) > 1500
    assert len(response.fuel_types) > 0
    assert len(response.brands) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_fuel_prices(client):
    """Integration test for fetching all fuel prices."""
    response = await client.get_fuel_prices()
    assert len(response.stations) > 1500
    assert len(response.prices) > 1500
    # Optional spot-check for first station
    first_station = response.stations[0]
    assert first_station.name
    assert first_station.code > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_fuel_prices_for_station(client):
    """Integration test for fetching fuel prices for a single station."""
    # Fetch reference data first to get a valid station code
    reference = await client.get_reference_data()
    station_id = reference.stations[0].code

    # Fetch prices for that station
    prices = await client.get_fuel_prices_for_station(station_id)
    assert len(prices) >= 1
    for price in prices:
        assert price.price > 0
        assert price.fuel_type is not None
        assert isinstance(price.last_updated, datetime)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_fuel_prices_within_radius(client):
    """Integration test for fetching fuel prices within a radius of a location."""
    # Example coordinates: Sydney CBD
    latitude = -33.8688
    longitude = 151.2093
    radius = 1000  # meters
    fuel_type = "E10"

    results = await client.get_fuel_prices_within_radius(
        latitude=latitude,
        longitude=longitude,
        radius=radius,
        fuel_type=fuel_type,
    )
    assert len(results) >= 1
    for station_price in results:
        assert station_price.station.code > 0
        assert station_price.price.price > 0
        assert station_price.price.fuel_type == fuel_type
