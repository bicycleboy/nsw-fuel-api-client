#!/usr/bin/env python3
"""Demo script for nsw-fuel-api-client that loads credentials from a file."""

import logging
from pathlib import Path
from typing import Tuple
import asyncio
from aiohttp import ClientSession

from nsw_fuel.client import FuelCheckClient, StationPrice # adjust this import if necessary
from nsw_fuel.dto import Price, Station

SECRETS_FILE = Path("secrets")
logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)


def load_secrets() -> Tuple[str, str]:
    """Load API key and secret from a local 'secrets' file."""
    if not SECRETS_FILE.exists():
        raise FileNotFoundError(
            f"Secrets file not found: {SECRETS_FILE}. Expected format: <key>, <secret>"
        )
    with open(SECRETS_FILE, "r", encoding="utf-8") as file:
        line = file.readline().strip()
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 2:
            raise ValueError(
                "Secrets file format invalid. Expected: <key>, <secret> on one line."
            )
        return parts[0], parts[1]



async def main() -> None:
    """Run demonstration."""
    try:
        api_key, api_secret = load_secrets()
    except Exception as exc:
        _LOGGER.error("Error loading secrets: %s", exc)
        return

    # Create an aiohttp session
    async with ClientSession() as session:
        client = FuelCheckClient(session=session, client_id=api_key, client_secret=api_secret)
        station_code = "18798"

        try:
            _LOGGER.info("Fetching price data for station %s...", station_code)
            prices = await client.get_fuel_prices_for_station(station_code)
        except Exception as exc:
            _LOGGER.error("Failed to fetch station prices: %s", exc)
            return

        # Print results
        print(f"✅ Prices for station {station_code}:")
        for price in prices:
            print(
                f"  {price.fuel_type}: {price.price} c/L "
                f"(Last updated: {price.last_updated})"
            )


        # Parameters
        longitude = 149.14
        latitude = -35.27
        radius = 15
        fuel_type = "E10"

        try:
            prices: list[StationPrice] = await client.get_fuel_prices_within_radius(
                named_location="18798",
                latitude=latitude,
                longitude=longitude,
                radius=radius,
                fuel_type=fuel_type,
            )
            for item in prices:
                station = item.station        # Correct attribute
                price = item.price            # Correct attribute

                print(
                    f"{station.brand} {station.name} (${price.price}) "
                    f"Station Code: {station.code}, Fuel Type: {price.fuel_type}, "
                    f"Last Updated: {price.last_updated}"
                )
        except Exception as e:
            _LOGGER.error("Error fetching prices within radius: %s", e)

        # Fetch price trends
            try:
                trends = await client.async_get_fuel_price_trends(
                    latitude=latitude,
                    longitude=longitude,
                    fuel_types=[fuel_type],
                )
                print("\n✅ Fuel price trends:")
                for variance in trends.variances:
                    print(f"  {variance.fuel_type}: {variance.variance} c/L variance")
                for avg in trends.average_prices:
                    print(f"  {avg.fuel_type}: average {avg.price} c/L")
            except Exception as e:
                _LOGGER.error("Error fetching fuel price trends: %s", e)



if __name__ == "__main__":
    asyncio.run(main())