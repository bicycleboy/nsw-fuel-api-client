"""Script to explore NSW Fuel Check API."""

import asyncio
import logging
import os
from datetime import UTC, datetime, timedelta

from aiohttp import ClientSession
from nsw_fuel.client import (
    NSWFuelApiClient,
    StationPrice,
)

logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)


def load_secrets() -> tuple[str, str]:
    """Get Fuel Check API key and secret."""
    key = os.getenv("NSWFUELCHECKAPI_KEY", "")
    secret = os.getenv("NSWFUELCHECKAPI_SECRET", "")

    if not key or not secret:
        msg = (
            f"NSWFUELCHECKAPI_KEY={key} and or NSWFUELCHECKAPI_SECRET={secret} not set"
        )
        raise KeyError(msg)
    return key, secret


async def main() -> None:
    """Run demonstration."""
    try:
        api_key, api_secret = load_secrets()
    except Exception as exc:
        _LOGGER.exception("Error loading secrets: %s", exc)
        return

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
        # Sydney
        longitude = 151.2
        latitude = -33.86
        # Hobart
        # longitude = 147.33
        # latitude = -42.88
        radius = 25
        fuel_type = "E10"

        try:
            sp: list[StationPrice] = await client.get_fuel_prices_within_radius(
                latitude=latitude,
                longitude=longitude,
                radius=radius,
                fuel_type=fuel_type,
            )
            for item in sp:
                station = item.station
                price = item.price

                print(
                    f"{station.brand} {station.name} (${price.price}) "
                    f"Station Code: {station.code}, Fuel Type: {price.fuel_type}, "
                    f"Last Updated: {price.last_updated}"
                )
        except Exception as e:
            _LOGGER.error("Error fetching prices within radius: %s", e)

        _LOGGER.info("Fetching reference data modified since yesterday...")

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
                    data_to_print = response  # fallback if already serializable  # noqa: F841

                # Pretty-print JSON
                #           print(json.dumps(data_to_print, indent=4, default=str))

                fuel_type_strings = [ft.name for ft in response.fuel_types]
                print(fuel_type_strings)

                print(f"✅ Reference Data Stations Count: {len(response.stations)}")  # noqa: T201

            except Exception as e:
                print(f"Error fetching reference data: {e}")


if __name__ == "__main__":
    asyncio.run(main())
