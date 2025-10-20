
from __future__ import annotations

import base64
import json
import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional, NamedTuple, Dict, Any

from .dto import (
    Price, Station, Variance, AveragePrice, FuelCheckError,
    GetReferenceDataResponse, GetFuelPricesResponse)

from .const import AUTH_URL, BASE_URL, PRICE_ENDPOINT, PRICES_ENDPOINT, REFERENCE_ENDPOINT, NEARBY_ENDPOINT, LOGGER

from aiohttp import (
    ClientConnectionError,
    ClientError,
    ClientResponseError,
    ClientSession,
    ClientTimeout,
)
UTC = timezone.utc
HTTP_UNAUTHORIZED = 401

PriceTrends = NamedTuple('PriceTrends', [
    ('variances', List[Variance]),
    ('average_prices', List[AveragePrice])
])

StationPrice = NamedTuple('StationPrice', [
    ('price', Price),
    ('station', Station)
])
# Need to rationalise exceptions and FuelCheckError
class NSWFuelApiClientError(Exception):
    """General API error."""


class NSWFuelApiClientAuthError(NSWFuelApiClientError):
    """Authentication failure."""


class FuelCheckClient():
    """API client for NSW FuelCheck."""
    def __init__(
        self, session: ClientSession, client_id: str, client_secret: str
    ) -> None:
        """Initialize with aiohttp session and client credentials."""
        self._session = session
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: str | None = None
        self._token_expiry: float = 0

    def _format_dt(self, dt: datetime.datetime) -> str:
        return dt.strftime('%d/%m/%Y %I:%M:%S %p')


    async def async_get_token(self) -> str | None:
        """Get or refresh OAuth2 token from the NSW Fuel API."""
        LOGGER.debug("async_get_token called")
        now = time.time()

        # Refresh if no token or it will expire soon
        if not self._token or now > (self._token_expiry - 60):
            LOGGER.debug("Refreshing NSW Fuel API token")

            params = {"grant_type": "client_credentials"}
            # Base64 encode client_id:client_secret
            auth_str = f"{self._client_id}:{self._client_secret}"
            auth_bytes = auth_str.encode("utf-8")
            auth_b64 = base64.b64encode(auth_bytes).decode("utf-8")
            headers = {
                "Accept": "application/json",
                "Authorization": f"Basic {auth_b64}",
            }
            LOGGER.debug("Instance of FuelCheckClient created: id=%s", id(self))

            try:
                async with self._session.get(
                    AUTH_URL, params=params, headers=headers
                ) as resp:
                    text = await resp.text()
                    LOGGER.debug(
                        "Token response status=%s, content_type=%s, params=%s",
                        resp.status,
                        resp.content_type,
                        {"grant_type": params["grant_type"]},  # redact secret
                    )
                resp.raise_for_status()

                # Some NSW APIs mislabel JSON as x-www-form-urlencoded
                if "application/json" in resp.content_type:
                    try:
                        result = await resp.json()
                    except ClientConnectionError as err:
                        LOGGER.exception("Connection dropped while parsing token")
                        msg = "Connection lost during token fetch"
                        raise NSWFuelApiClientError(msg) from err
                else:
                    LOGGER.warning(
                        "Expected application/json, got %s", resp.content_type
                    )
                    try:
                        result = json.loads(text)
                    except json.JSONDecodeError as err:
                        msg = "Failed to parse token response"
                        raise NSWFuelApiClientError(msg) from err

            except ClientResponseError as err:

                if err.status == HTTP_UNAUTHORIZED:
                    msg = "Invalid NSW Fuel API credentials"
                    raise NSWFuelApiClientAuthError(msg) from err
                msg = f"Token request failed with status {err.status}: {err.message}"
                raise NSWFuelApiClientError(msg) from err

            except OSError as err:
                msg = f"Network error fetching NSW Fuel token: {err}"
                raise NSWFuelApiClientError(msg) from err

            # Parse result and cache token
            access_token = result.get("access_token")
            if access_token is not None:
                self._token = access_token
                expires_in = int(result.get("expires_in", 3600))
                self._token_expiry = now + expires_in
                LOGGER.debug("Token acquired; expires in %s seconds", expires_in)
            else:
                self._token = None
                msg = "No access_token in NSW Fuel token response"
                raise NSWFuelApiClientError(msg)


        return self._token


    async def _async_request(
        self,
        path: str,
        method: str = "GET",
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> Any:
        """Perform an authorized HTTP request (GET or POST) to the NSW Fuel API."""
        token = await self.async_get_token()
        if not token:
            raise NSWFuelApiClientError("No access token available for NSW Fuel API request")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "apikey": self._client_id,
            "TransactionID": str(uuid.uuid4()),
            "RequestTimestamp": datetime.now(timezone.utc).isoformat(),
        }
        if extra_headers:
            headers.update(extra_headers)

        url = f"{BASE_URL}{path}"

        # Redact sensitive info for logging
        redacted_headers = {
            key: (
                f"{value[:6]}...{value[-4:]}" if key == "Authorization" and isinstance(value, str)
                else "REDACTED" if key == "apikey"
                else value
            )
            for key, value in headers.items()
        }
        LOGGER.info("Requesting %s with params=%s, headers=%s", url, params, redacted_headers)

        try:
            # Use aiohttp session for GET or POST
            async with self._session.request(
                method.upper(),
                url,
                headers=headers,
                params=params,
                json=json,
                timeout=ClientTimeout(total=30),
            ) as resp:
                status = resp.status
                try:
                    data = await resp.json(content_type=None)
                except Exception:  # noqa: BLE001
                    data = await resp.text()

                # Avoid logging large reference data
                if path != REFERENCE_ENDPOINT:
                    LOGGER.debug("API Response %s: %s", status, data)
                else:
                    LOGGER.debug("API Response %s", status)

                # Handle 401: refresh token and retry once
                if status == 401:
                    LOGGER.warning("401 Unauthorized, refreshing token...")
                    self._token = None
                    token = await self.async_get_token()
                    if not token:
                        raise NSWFuelApiClientAuthError("Failed to refresh token after 401")

                    headers["Authorization"] = f"Bearer {token}"
                    async with self._session.request(
                        method.upper(),
                        url,
                        headers=headers,
                        params=params,
                        json=json,
                        timeout=ClientTimeout(total=30),
                    ) as retry:
                        retry_status = retry.status
                        try:
                            retry_data = await retry.json(content_type=None)
                        except Exception:  # noqa: BLE001
                            retry_data = await retry.text()
                        LOGGER.debug("Retry Response %s: %s", retry_status, retry_data)
                        retry.raise_for_status()
                        return retry_data

                resp.raise_for_status()
                return data

        except ClientResponseError as err:
            if err.status == 401:
                raise NSWFuelApiClientAuthError("Authentication failed during request") from err
            raise NSWFuelApiClientError(f"HTTP error {err.status}: {err.message}") from err

        except ClientError as err:
            raise NSWFuelApiClientError(f"Connection error: {err}") from err

        except Exception as err:
            raise NSWFuelApiClientError(f"Unexpected error: {err}") from err


    async def get_fuel_prices(self) -> GetFuelPricesResponse:
        """Fetch fuel prices for all stations asynchronously.

        Raises:
            FuelCheckError: If the API request fails or the response is invalid.
        """
        # Perform the async GET request
        response: dict[str, Any] = await self._async_request(
            path=PRICES_ENDPOINT,
            params=None,
        )

        # Validate that response contains data
        if not response:
            raise FuelCheckError("No fuel prices returned from the API")

        # Deserialize the response into a structured object
        return GetFuelPricesResponse.deserialize(response)
    
    async def get_fuel_prices_for_station(
        self,
        station_code: str,
    ) -> List[Price]:
        """Fetch the fuel prices for a specific fuel station asynchronously."""
        # Perform the authorized GET request
        response: dict[str, Any] = await self._async_request(
          PRICE_ENDPOINT.format(station_code=station_code)
        )

        # Check that the response contains 'prices'
        prices_data = response.get("prices")
        if not prices_data:
           raise FuelCheckError(f"No prices found for station {station_code}")

        # Deserialize each price entry into a Price object
        return [Price.deserialize(p) for p in prices_data]
    
    async def get_fuel_prices_within_radius(
        self,
        latitude: float,
        longitude: float,
        radius: int,
        fuel_type: str,
        brands: Optional[List[str]] = None,
        named_location: str | None = None,
        sort_by: str = "price",
        sort_ascending: bool = True,

    ) -> List[StationPrice]:
        """Fetch all fuel prices within the specified radius asynchronously.

        Args:
            latitude: Latitude of the center point.
            longitude: Longitude of the center point.
            radius: Radius in meters/kilometers to search.
            fuel_type: Fuel type code (e.g., 'U91', 'E10').
            brands: Optional list of brand names to filter.

        Raises:
            FuelCheckError: If the API request fails or data is invalid.
        """
        payload: dict[str, Any] = {
            "fueltype": fuel_type,
            "brand": brands or [],
            "namedlocation": named_location or "",
            "latitude": str(latitude),   # API expects strings
            "longitude": str(longitude),
            "radius": str(radius),       # API also expects a string here
            "sortby": sort_by,
            "sortascending": str(sort_ascending).lower(),  # "true"/"false"
        }

        # Perform the async POST request
        response: dict[str, Any] = await self._async_request(
            path=NEARBY_ENDPOINT,
            params=None,
            method="POST",
            json=payload,
            extra_headers={"Content-Type": "application/json"},
        )

        # Log the raw API response
        LOGGER.debug(
            "Raw nearby fuel prices response for lat=%s lon=%s: %s",
            latitude,
            longitude,
            response,
        )

        # Validate response
        stations_data = response.get("stations")
        prices_data = response.get("prices")
        if not stations_data or not prices_data:
            raise FuelCheckError(
                f"No stations or prices found for location ({latitude}, {longitude})"
            )

        # Deserialize stations
        stations: dict[str, Station] = {
            station["code"]: Station.deserialize(station) for station in stations_data
        }

        # Deserialize prices and attach station
        station_prices: List[StationPrice] = []
        for serialized_price in prices_data:
            price = Price.deserialize(serialized_price)
            station_obj = stations.get(price.station_code)
            if station_obj:
                station_prices.append(StationPrice(price=price, station=station_obj))

        # Log the final deserialized data
        LOGGER.debug(
            "Deserialized nearby station prices: %s",
            station_prices,
        )

        return station_prices

  
    async def get_reference_data(
        self,
        modified_since: Optional[datetime] = None,
        states: Optional[list[str]] = None
    ) -> GetReferenceDataResponse:
        """
        Fetch API reference data.

        :param modified_since: Optional datetime to fetch only data modified since this timestamp.
                            If None, all reference data will be returned.
        :raises FuelCheckError: If the API request fails or returns invalid data.
        :return: Deserialized GetReferenceDataResponse object.
        """

        headers = {}
        if modified_since:
            headers["if-modified-since"] = self._format_dt(modified_since)
        # Add states as extra header if provided
        params = {}
        if states:
            # Join list into comma-separated string if needed by API
            params["states"] = states

        # Make the authorized GET request
        response_data = await self._async_request(
            REFERENCE_ENDPOINT,
            params=params,
            extra_headers=headers
        )

        if not response_data:  # handle empty or invalid response
            raise FuelCheckError("Empty response from reference data endpoint")

        # Deserialize JSON into your data model
        return GetReferenceDataResponse.deserialize(response_data)
