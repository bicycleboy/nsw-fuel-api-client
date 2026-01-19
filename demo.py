#!/usr/bin/env python3
"""Demo script for nsw-fuel-api-client that loads credentials from a file."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
import os
from pathlib import Path
from typing import Tuple
import json

from aiohttp import ClientSession
from sqlalchemy import false
from nsw_fuel.client import (
    NSWFuelApiClient,
    StationPrice,
)


logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)


def load_secrets() -> Tuple[str, str]:
    key = os.getenv("NSWFUELCHECKAPI_KEY", "")
    secret = os.getenv("NSWFUELCHECKAPI_SECRET", "")

    if not key or not secret:
        msg = f"KEY={key} and or SECRET={secret} not set"
        raise FileNotFoundError(msg)
    return key, secret


async def main() -> None:
    """Run demonstration."""
    try:
        api_key, api_secret = load_secrets()
    except Exception as exc:
        _LOGGER.exception("Error loading secrets: %s", exc)
        return

    # Create an aiohttp session
    async with ClientSession() as session:
        client = NSWFuelApiClient(
            session=session, client_id=api_key, client_secret=api_secret
        )
        station_code = "18813"

        try:
            _LOGGER.info("Fetching price data for station %s...", station_code)
            prices = await client.get_fuel_prices_for_station(
                station_code,
                state="NSW",
            )
        except Exception as exc:
            _LOGGER.exception("Failed to fetch station prices: %s", exc)
            return

        # Write the token to a file so we can use it in the nsw api site to understand the API
        if client._token:  # make sure token exists
            with open("token", "w") as f:
                f.write(client._token)
            print("Token written to 'token' file.")
        else:
            print("Token is not available.")

        # Print results
        print(f"✅ Prices for station {station_code}:")
        for price in prices:
            print(
                f"  {price.fuel_type}: {price.price} c/L "
                f"(Last updated: {price.last_updated})"
            )

        # Parameters
        # Durras
        longitude = 150.29
        latitude = -35.66
        # Hobart
        #longitude = 147.33
        #latitude = -42.88
        radius = 105
        fuel_type = "E10-U91"

        try:
            prices: list[StationPrice] = await client.get_fuel_prices_within_radius(
                latitude=latitude,
                longitude=longitude,
                radius=radius,
                fuel_type=fuel_type,
            )
            for item in prices:
                station = item.station
                price = item.price

                print(
                    f"{station.brand} {station.name} (${price.price}) "
                    f"Station Code: {station.code}, Fuel Type: {price.fuel_type}, "
                    f"Last Updated: {price.last_updated}"
                )
        except Exception as e:
            _LOGGER.error("Error fetching prices within radius: %s", e)

        # Fetch reference data
        _LOGGER.info("Fetching reference data modified since yesterday...")

        # Calculate "modified since yesterday"
        modified_since_dt = datetime.now(UTC) - timedelta(days=1)

        if False:
            # Call the function
            try:
                response = await client.get_reference_data(
                    modified_since=modified_since_dt, states="NSW"
                )

                # Convert the response to a dict if it has a `__dict__` or similar method
                # Otherwise, adjust based on how your response object stores data
                if hasattr(response, "__dict__"):
                    data_to_print = response.__dict__
                else:
                    data_to_print = response  # fallback if already serializable

                # Pretty-print JSON
                #           print(json.dumps(data_to_print, indent=4, default=str))

                fuel_type_strings = [ft.name for ft in response.fuel_types]
                print(fuel_type_strings)

                print(f"✅ Reference Data Stations Count: {len(response.stations)}")  # noqa: T201

            except Exception as e:
                print(f"Error fetching reference data: {e}")


if __name__ == "__main__":
    asyncio.run(main())
