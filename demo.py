#!/usr/bin/env python3
"""Demo script for nsw-fuel-api-client that loads credentials from a file."""

import logging
from pathlib import Path
from typing import Tuple

from nsw_fuel.client import FuelCheckClient  # adjust this import if necessary

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


def main() -> None:
    """Run demonstration."""
    try:
        api_key, api_secret = load_secrets()
    except Exception as exc:
        _LOGGER.error("Error loading secrets: %s", exc)
        return

    # Create NSW Fuel API client
    client = FuelCheckClient()

    # Example: choose a station code to query
    station_code = 20254

    try:
        _LOGGER.info("Fetching price data for station %d...", station_code)
        prices = client.get_fuel_prices_for_station(station_code)
    except Exception as exc:
        _LOGGER.error("Failed to fetch station prices: %s", exc)
        return

    # Print results
    print(f"✅ Prices for station {station_code}:")
    for price in prices:
        print(f"  {price.fuel_type}: {price.price} c/L (Last updated: {price.last_updated})")


if __name__ == "__main__":
    main()
