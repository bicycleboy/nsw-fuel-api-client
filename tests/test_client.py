import asyncio
import datetime
import json
import os
import re
import pytest
from aioresponses import aioresponses

from nsw_fuel.client import FuelCheckClient
from nsw_fuel.const import BASE_URL, PRICES_ENDPOINT, PRICE_ENDPOINT, NEARBY_ENDPOINT, REFERENCE_ENDPOINT
from nsw_fuel.dto import FuelCheckError

# Paths to fixture files
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
ALL_PRICES_FILE = os.path.join(FIXTURES_DIR, "all_prices.json")
LOVS_FILE = os.path.join(FIXTURES_DIR, "lovs.json")


@pytest.mark.asyncio
async def test_get_fuel_prices(session, mock_token):
    """Test fetching all fuel prices."""
    url = f"{BASE_URL}{PRICES_ENDPOINT}"

    with open(ALL_PRICES_FILE) as f:
        fixture_data = json.load(f)

    mock_token.get(url, payload=fixture_data)

    client = FuelCheckClient(session=session, client_id="key", client_secret="secret")
    response = await client.get_fuel_prices()

    assert len(response.stations) == 2
    assert len(response.prices) == 5
    assert response.stations[0].name == "Cool Fuel Brand Hurstville"
    assert response.stations[1].name == "Fake Fuel Brand Kogarah"
    assert round(response.stations[1].latitude, 0) == -31
    assert round(response.stations[1].longitude, 0) == 152
    assert response.prices[0].fuel_type == "DL"
    assert response.prices[1].fuel_type == "E10"
    assert response.prices[1].station_code == 1
    assert response.prices[3].fuel_type == "P95"
    assert response.prices[3].station_code == 2


@pytest.mark.asyncio
async def test_get_fuel_prices_for_station(session, mock_token):
    """Test fetching prices for a single station."""
    station_code = 100
    url = f"{BASE_URL}{PRICE_ENDPOINT.format(station_code=station_code)}"
    mock_token.get(
        url,
        payload={
            "prices": [
                {"fueltype": "E10", "price": 146.9, "lastupdated": "02/06/2018 02:03:04"},
                {"fueltype": "P95", "price": 150.0, "lastupdated": "02/06/2018 02:03:04"},
            ]
        },
    )

    client = FuelCheckClient(session=session, client_id="key", client_secret="secret")
    result = await client.get_fuel_prices_for_station(station_code)

    assert len(result) == 2
    assert result[0].fuel_type == "E10"
    assert result[0].price == 146.9
    assert result[0].last_updated == datetime.datetime(
        day=2, month=6, year=2018, hour=2, minute=3, second=4
    )


@pytest.mark.asyncio
async def test_get_fuel_prices_within_radius(session, mock_token):
    """Test fetching prices within radius."""
    url = f"{BASE_URL}{NEARBY_ENDPOINT}"

    mock_token.post(
        url,
        payload={
            "stations": [
                {
                    "stationid": "SAAAAAA",
                    "brandid": "BAAAAAA",
                    "brand": "Cool Fuel Brand",
                    "code": 678,
                    "name": "Cool Fuel Brand Luxembourg",
                    "address": "123 Fake Street",
                    "location": {"latitude": -33.987, "longitude": 151.334},
                },
                {
                    "stationid": "SAAAAAB",
                    "brandid": "BAAAAAB",
                    "brand": "Fake Fuel Brand",
                    "code": 679,
                    "name": "Fake Fuel Brand Luxembourg",
                    "address": "123 Fake Street",
                    "location": {"latitude": -33.587, "longitude": 151.434},
                },
                {
                    "stationid": "SAAAAAB",
                    "brandid": "BAAAAAB",
                    "brand": "Fake Fuel Brand2",
                    "code": 880,
                    "name": "Fake Fuel Brand2 Luxembourg",
                    "address": "123 Fake Street",
                    "location": {"latitude": -33.687, "longitude": 151.234},
                },
            ],
            "prices": [
                {
                    "stationcode": 678,
                    "fueltype": "P95",
                    "price": 150.9,
                    "priceunit": "litre",
                    "description": None,
                    "lastupdated": "2018-06-02 00:46:31",
                },
                {
                    "stationcode": 678,
                    "fueltype": "P95",
                    "price": 130.9,
                    "priceunit": "litre",
                    "description": None,
                    "lastupdated": "2018-06-02 00:46:31",
                },
                {
                    "stationcode": 880,
                    "fueltype": "P95",
                    "price": 155.9,
                    "priceunit": "litre",
                    "description": None,
                    "lastupdated": "2018-06-02 00:46:31",
                },
            ],
        },
    )

    client = FuelCheckClient(session=session, client_id="key", client_secret="secret")
    result = await client.get_fuel_prices_within_radius(
        latitude=-33.0, longitude=151.0, radius=10, fuel_type="E10"
    )

    assert len(result) == 3
    assert result[0].station.code == 678
    assert round(result[0].station.latitude, 3) == -33.987
    assert round(result[0].station.longitude, 3) == 151.334
    assert result[0].price.price == 150.9


@pytest.mark.asyncio
async def test_get_reference_data(session, mock_token):
    """Test fetching reference data."""
    url = f"{BASE_URL}{REFERENCE_ENDPOINT}"
    with open(LOVS_FILE) as f:
        fixture_data = json.load(f)

    mock_token.get(url, payload=fixture_data)

    client = FuelCheckClient(session=session, client_id="key", client_secret="secret")
    response = await client.get_reference_data()

    assert len(response.brands) == 2
    assert len(response.fuel_types) == 2
    assert len(response.stations) == 2
    assert len(response.trend_periods) == 2
    assert len(response.sort_fields) == 2
    assert response.brands[0] == "Cool Fuel Brand"
    assert response.fuel_types[0].code == "E10"
    assert response.fuel_types[0].name == "Ethanol 94"
    assert response.stations[0].name == "Cool Fuel Brand Hurstville"
    assert response.trend_periods[0].period == "Day"
    assert response.trend_periods[0].description == "Description for day"
    assert response.sort_fields[0].code == "Sort 1"
    assert response.sort_fields[0].name == "Sort field 1"


@pytest.mark.asyncio
async def test_get_fuel_prices_server_error(session, mock_token):
    """Test 500 server error for all fuel prices."""
    url = f"{BASE_URL}{PRICES_ENDPOINT}"
    mock_token.get(url, status=500, body="Internal Server Error.")

    client = FuelCheckClient(session=session, client_id="key", client_secret="secret")
    with pytest.raises(FuelCheckError) as exc:
        await client.get_fuel_prices()

    assert "Internal Server Error" in str(exc.value)


@pytest.mark.asyncio
async def test_get_fuel_prices_for_station_client_error(session, mock_token):
    """Test 400 client error for a single station."""
    station_code = 21199
    url = f"{BASE_URL}{PRICE_ENDPOINT.format(station_code=station_code)}"
    mock_token.get(
        url,
        status=400,
        payload={
            "errorDetails": [
                {
                    "code": "E0014",
                    "description": f'Invalid service station code "{station_code}"'
                }
            ]
        },
    )

    client = FuelCheckClient(session=session, client_id="key", client_secret="secret")
    with pytest.raises(FuelCheckError) as exc:
        await client.get_fuel_prices_for_station(station_code)

    assert f'Invalid service station code "{station_code}"' in str(exc.value)


@pytest.mark.asyncio
async def test_get_fuel_prices_within_radius_server_error(session, mock_token):
    """Test 500 server error for nearby fuel prices."""
    url = f"{BASE_URL}{NEARBY_ENDPOINT}"
    mock_token.post(url, status=500, body="Internal Server Error.")

    client = FuelCheckClient(session=session, client_id="key", client_secret="secret")
    with pytest.raises(FuelCheckError) as exc:
        await client.get_fuel_prices_within_radius(
            latitude=-33.0, longitude=151.0, radius=10, fuel_type="E10"
        )

    assert "Internal Server Error" in str(exc.value)


@pytest.mark.asyncio
async def test_get_reference_data_client_error(session, mock_token):
    """Test 400 client error for reference data."""
    url = f"{BASE_URL}{REFERENCE_ENDPOINT}"
    mock_token.get(
        url,
        status=400,
        payload={
            "errorDetails": {
                "code": "-2146233033",
                "message": "String was not recognized as a valid DateTime."
            }
        },
    )

    client = FuelCheckClient(session=session, client_id="key", client_secret="secret")
    with pytest.raises(FuelCheckError) as exc:
        await client.get_reference_data()

    assert "String was not recognized as a valid DateTime" in str(exc.value)


@pytest.mark.asyncio
async def test_get_reference_data_server_error(session, mock_token):
    """Test 500 server error for reference data."""
    url = f"{BASE_URL}{REFERENCE_ENDPOINT}"
    mock_token.get(url, status=500, body="Internal Server Error.")

    client = FuelCheckClient(session=session, client_id="key", client_secret="secret")
    with pytest.raises(FuelCheckError) as exc:
        await client.get_reference_data()

    assert "Internal Server Error" in str(exc.value)
