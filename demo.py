#!/usr/bin/env python3
"""Demo script for nsw-fuel-api-client that loads credentials from a file."""

from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
from typing import Tuple
import asyncio
from aiohttp import ClientSession

from nsw_fuel.client import FuelCheckClient, StationPrice # adjust this import if necessary


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
        longitude = 149.14
        latitude = -35.27
        radius = 15
        fuel_type = "E10"

        try:
            prices: list[StationPrice] = await client.get_fuel_prices_within_radius(
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

        # Fetch reference data
        _LOGGER.info("Fetching reference data modified since yesterday...") 

        # Calculate "modified since yesterday"
        modified_since_dt = datetime.now(timezone.utc) - timedelta(days=1)

        # Call the function
        try:
            response = await client.get_reference_data(modified_since=modified_since_dt, states="TAS")

            # Convert the response to a dict if it has a `__dict__` or similar method
            # Otherwise, adjust based on how your response object stores data
            if hasattr(response, "__dict__"):
                data_to_print = response.__dict__
            else:
                data_to_print = response  # fallback if already serializable

            # Pretty-print JSON
#            print(json.dumps(data_to_print, indent=4, default=str))
            print(f"✅ Reference Data Stations Count: {len(response.stations)}")

        except Exception as e:
            print(f"Error fetching reference data: {e}")



if __name__ == "__main__":
    asyncio.run(main())