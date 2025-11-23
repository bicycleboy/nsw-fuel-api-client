"""NSW Fuel Check API, main API interface."""
from __future__ import annotations

import base64
import json
import time
import uuid
from datetime import UTC, datetime
from typing import Any, NamedTuple

from aiohttp import (
    ClientConnectionError,
    ClientError,
    ClientResponse,
    ClientResponseError,
    ClientSession,
    ClientTimeout,
    ContentTypeError,
)

from .const import (
    AUTH_URL,
    BASE_URL,
    DEFAULT_TIMEOUT,
    HTTP_CLIENT_SERVER_ERRORS,
    HTTP_INTERNAL_SERVER_ERROR,
    HTTP_UNAUTHORIZED,
    LOGGER,
    NEARBY_ENDPOINT,
    PRICE_ENDPOINT,
    PRICES_ENDPOINT,
    REFERENCE_ENDPOINT,
)
from .dto import (
    AveragePrice,
    GetFuelPricesResponse,
    GetReferenceDataResponse,
    Price,
    Station,
    Variance,
)


class PriceTrends(NamedTuple):
    """PriceTrends."""

    variances: list[Variance]
    average_prices: list[AveragePrice]

class StationPrice(NamedTuple):
    """StationPrice."""

    price: Price
    station: Station


class NSWFuelApiClientError(Exception):
    """Base class for all NSW Fuel API errors."""


class NSWFuelApiClientAuthError(NSWFuelApiClientError):
    """Authentication failure (invalid or expired credentials)."""


class NSWFuelApiClientConnectionError(NSWFuelApiClientError):
    """Connection or server availability issue."""


class NSWFuelApiClient:
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

    def _format_dt(self, dt: datetime) -> str:
        return dt.strftime("%d/%m/%Y %I:%M:%S %p")

    @staticmethod
    def _extract_error_details(data: Any) -> str | None:
        """Extract readable error details message from API response data."""
        if not isinstance(data, dict):
            return None

        ed = data.get("errorDetails")
        if isinstance(ed, list) and ed:
            return ed[0].get("description") or ed[0].get("message")
        if isinstance(ed, dict):
            return ed.get("description") or ed.get("message")
        return None

    async def _async_get_token(self) -> str | None:
        """
        Get or refresh OAuth2 token from the NSW Fuel API.

        Raises:
            NSWFuelApiClientAuthError: If authentication fails.
            NSWFuelApiClientError: For all other token fetch errors.

        """
        LOGGER.debug("_async_get_token called ok")
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
            LOGGER.debug("Instance of NSWFuelApiClient created: id=%s", id(self))

            try:
                async with self._session.get(
                    AUTH_URL, params=params, headers=headers
                ) as response:
                    response.raise_for_status()

                    text = await response.text()

                    LOGGER.debug(
                        "Token response status=%s, content_type=%s, params=%s",
                        response.status,
                        response.content_type,
                        {"grant_type": params["grant_type"]},  # redact secret
                    )

                try:
                    if "application/json" in response.content_type:
                        result = await response.json()
                    else:
                        LOGGER.warning(
                            "Expected application/json, got %s", response.content_type
                        )
                        result = json.loads(text)
                except (json.JSONDecodeError, ValueError) as err:
                    msg = "Failed to parse token response JSON"
                    raise NSWFuelApiClientError(msg) from err
                except ClientConnectionError as err:
                    LOGGER.exception("Connection dropped while parsing token")
                    msg = "Connection lost during token fetch"
                    raise NSWFuelApiClientError(msg) from err

            except ClientResponseError as err:
                if err.status == HTTP_UNAUTHORIZED:
                    msg = "Invalid NSW Fuel Check API credentials"
                    raise NSWFuelApiClientAuthError(msg) from err
                msg = f"Token request failed with status {err.status}: {err.message}"
                raise NSWFuelApiClientError(msg) from err

            except OSError as err:
                msg = f"Network error fetching NSW Fuel Check token: {err}"
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
                msg = "No access_token in NSW Fuel Check token response"
                raise NSWFuelApiClientError(msg)

        return self._token

    async def _async_request(  # noqa: PLR0912, PLR0915
        self,
        path: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> Any:
        """
        Perform an authorized HTTP request (GET or POST) to the NSW Fuel API.

        Raises:
            NSWFuelApiClientAuthError: If authentication fails.
            NSWFuelApiClientConnectionError: If network or server issues occur.
            NSWFuelApiClientError: For all other API or data validation errors.

        """
        max_retries = 1
        attempt = 0

        def _build_headers(token: str) -> dict[str, str]:
            base_headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "apikey": self._client_id,
                "TransactionID": str(uuid.uuid4()),
                "RequestTimestamp": datetime.now(UTC).isoformat(),
            }
            if extra_headers:
                base_headers.update(extra_headers)
            return base_headers

        async def _parse_response(response: ClientResponse) -> Any:
            try:
                return await response.json(encoding="utf-8", content_type=None)
            except (ContentTypeError, json.JSONDecodeError):
                return await response.text()

        async def _handle_http_error(
            status: int, data: Any, response: ClientResponse
        ) -> None:
            error_details_msg = self._extract_error_details(data)

            if status == HTTP_UNAUTHORIZED:
                raise NSWFuelApiClientAuthError(
                    error_details_msg or "Authentication failed during request"
                )
            if status >= HTTP_INTERNAL_SERVER_ERROR:
                raise NSWFuelApiClientConnectionError(
                    error_details_msg or f"Server error {status}: {response.reason}"
                )
            raise NSWFuelApiClientError(
                error_details_msg or f"HTTP error {status}: {response.reason}"
            )

        while attempt <= max_retries:
            token = await self._async_get_token()
            if not token:
                msg = "No access token available for NSW Fuel API request"
                raise NSWFuelApiClientError(msg)

            headers = _build_headers(token)
            url = f"{BASE_URL}{path}"

            try:
                async with self._session.request(
                    method.upper(),
                    url,
                    headers=headers,
                    params=params,
                    json=json_body,
                    timeout=ClientTimeout(total=DEFAULT_TIMEOUT),
                ) as response:
                    status = response.status
                    data = await _parse_response(response)

                    if status == HTTP_UNAUTHORIZED:
                        LOGGER.warning("401 Unauthorized, refreshing token, retry...")
                        self._token = None
                        attempt += 1
                        if attempt > max_retries:
                            msg = "Failed to authenticate after retry"
                            raise NSWFuelApiClientAuthError(msg)  # noqa: TRY301
                        continue

                    if status >= HTTP_CLIENT_SERVER_ERRORS:
                        await _handle_http_error(status, data, response)

                    return data

            except ClientResponseError as err:
                error_details_msg = None
                try:
                    if err.response is not None:
                        error_json = await err.response.json(content_type=None)
                        error_details_msg = self._extract_error_details(error_json)
                except (ContentTypeError, json.JSONDecodeError):
                    pass

                if err.status == HTTP_UNAUTHORIZED:
                    msg = error_details_msg or "Authentication failed during request"
                    raise NSWFuelApiClientAuthError(
                        msg
                    ) from err
                if err.status >= HTTP_INTERNAL_SERVER_ERROR:
                    msg = (
                        error_details_msg or f"Server error {err.status}: {err.message}"
                    )
                    raise NSWFuelApiClientConnectionError(
                        msg
                    ) from err
                msg = error_details_msg or f"HTTP error {err.status}: {err.message}"
                raise NSWFuelApiClientError(
                    msg
                ) from err

            except ClientError as err:
                msg = f"Connection error: {err}"
                raise NSWFuelApiClientError(msg) from err

            except NSWFuelApiClientError:
                raise

            except Exception as err:
                msg = f"{err}"
                raise NSWFuelApiClientError(msg) from err

        # If somehow no return occurred  raise generic error
        msg = "Failed to perform request"
        raise NSWFuelApiClientError(msg)

    async def get_fuel_prices(self) -> GetFuelPricesResponse:
        """
        Fetch all NSW fuel prices.

        Raises:
            NSWFuelApiClientAuthError: If authentication fails.
            NSWFuelApiClientConnectionError: If network or server issues occur.
            NSWFuelApiClientError: For all other API or data validation errors.

        """
        try:
            response: dict[str, Any] = await self._async_request(
                path=PRICES_ENDPOINT,
                params=None,
            )

        except (
            NSWFuelApiClientAuthError,
            NSWFuelApiClientConnectionError,
            NSWFuelApiClientError,
        ):
            # Pass through unchanged so HA can handle login issues distinctly
            raise

        except Exception as err:
            LOGGER.debug("Caught unexpected Exception: %s - %s", type(err), err)
            msg = "Unexpected failure fetching fuel prices: %s"
            raise NSWFuelApiClientError(msg, err) from err

        if not response:
            msg = "No data returned from NSW Fuel API"
            raise NSWFuelApiClientError(msg)

        # Validate structure
        if "prices" not in response or "stations" not in response:
            msg = "Malformed response: missing required fields"
            raise NSWFuelApiClientError(msg)

        return GetFuelPricesResponse.deserialize(response)

    async def get_fuel_prices_for_station(
        self,
        station_code: str,
    ) -> list[Price]:
        """
        Fetch the fuel prices for a specific fuel station asynchronously.

        TODO: Need to pass in state as station ids not unique

        Raises:
            NSWFuelApiClientAuthError: If authentication fails.
            NSWFuelApiClientConnectionError: If network or server issues occur.
            NSWFuelApiClientError: For all other API or data validation errors.

        """
        try:
            response: dict[str, Any] = await self._async_request(
                PRICE_ENDPOINT.format(station_code=station_code)
            )

        except (
            NSWFuelApiClientAuthError,
            NSWFuelApiClientConnectionError,
            NSWFuelApiClientError,
        ):
            # Pass through unchanged so HA can handle issues distinctly
            raise

        except Exception as err:
            # Catch unexpected parsing or logic issues
            msg = f"Unexpected failure getting station prices for {station_code}: {err}"
            raise NSWFuelApiClientError(msg) from err

        # Validate response structure
        if not response or "prices" not in response:
            msg = f"Malformed or empty response for station {station_code}"
            raise NSWFuelApiClientError(msg)

        prices_data = response.get("prices")
        if not prices_data:
            msg = f"No price data found for station {station_code}"
            raise NSWFuelApiClientError(msg)

        # Deserialize prices
        return [Price.deserialize(p) for p in prices_data]

    async def get_fuel_prices_within_radius(  # noqa: PLR0913
        self,
        latitude: float,
        longitude: float,
        radius: int,
        fuel_type: str,
        brands: list[str] | None = None,
        named_location: str | None = None,
        sort_by: str = "price",
        sort_ascending: bool = True,  # noqa: FBT001, FBT002
    ) -> list[StationPrice]:
        """
        Fetch all fuel prices within the specified radius asynchronously.

        Args:
            See also API definition at api.nsw.gov.au/Product/Index/22
            latitude: Latitude of the center point.
            longitude: Longitude of the center point.
            radius: Radius in meters/kilometers to search.
            fuel_type: Fuel type code (e.g., 'U91', 'E10').
            brands: Optional list of brand names to filter.
            named_location: Suburb or postcode
            sort_by: price or ?
            sort_ascending: true or false for decending

        Raises:
            NSWFuelApiClientAuthError: If authentication fails.
            NSWFuelApiClientConnectionError: If network or server issues occur.
            NSWFuelApiClientError: For all other API or data validation errors.

        """
        try:
            payload: dict[str, Any] = {
                "fueltype": fuel_type,
                "brand": brands or [],
                "namedlocation": named_location or "",
                "latitude": str(latitude),  # API expects strings
                "longitude": str(longitude),
                "radius": str(radius),
                "sortby": sort_by,
                "sortascending": str(sort_ascending).lower(),  # "true"/"false"
            }

            # Perform the async POST request
            response: dict[str, Any] = await self._async_request(
                path=NEARBY_ENDPOINT,
                params=None,
                method="POST",
                json_body=payload,
                extra_headers={"Content-Type": "application/json"},
            )

            LOGGER.debug(
                "Raw nearby fuel prices response for lat=%s lon=%s: %s",
                latitude,
                longitude,
                response,
            )

        except (
            NSWFuelApiClientAuthError,
            NSWFuelApiClientConnectionError,
            NSWFuelApiClientError,
        ):
            # Pass through unchanged so HA can handle issues distinctly
            raise

        except Exception as err:
            msg = (
                f"Unexpected error fetching nearby prices for "
                f"({latitude}, {longitude}): {err}"
            )
            raise NSWFuelApiClientError(msg) from err

        # Validate structure
        if not response or "stations" not in response or "prices" not in response:
            msg = "Malformed or empty response for location "
            f"({latitude}, {longitude})"
            raise NSWFuelApiClientError(msg)

        stations_data = response.get("stations")
        prices_data = response.get("prices")
        if not stations_data or not prices_data:
            msg = f"No stations/prices found for location ({latitude}, {longitude})"
            raise NSWFuelApiClientError(msg)

        # Deserialize stations
        stations: dict[int, Station] = {
            int(station["code"]): Station.deserialize(station)
            for station in stations_data
        }

        # Deserialize prices and attach stations
        station_prices: list[StationPrice] = []
        for serialized_price in prices_data:
            try:
                price = Price.deserialize(serialized_price)
                if price.station_code is not None:
                    station_obj = stations.get(price.station_code)
                    if station_obj:
                        station_prices.append(
                            StationPrice(price=price, station=station_obj)
                        )
            except (KeyError, TypeError, ValueError) as parse_err:
                LOGGER.warning("Skipping malformed price entry: %s", parse_err)

        LOGGER.debug(
            "Deserialized %d nearby station prices for lat=%s lon=%s",
            len(station_prices),
            latitude,
            longitude,
        )

        return station_prices

    async def get_reference_data(
        self,
        modified_since: datetime | None = None,
        states: list[str] | None = None,
    ) -> GetReferenceDataResponse:
        """
        Fetch API reference data.

        :param modified_since:
            Optional datetime to fetch only data modified since this timestamp.
            If None, all reference data will be returned.
        :param states: Optional list of state abbreviations to filter results.
        :raises NSWFuelApiClientAuthError: If authentication fails.
        :raises NSWFuelApiClientConnectionError: If a network or transport error occurs.
        :raises NSWFuelApiClientError: For all other unexpected API or parsing errors.
        :return: Deserialized GetReferenceDataResponse object.
        """
        headers = {}
        if modified_since:
            headers["if-modified-since"] = self._format_dt(modified_since)

        params = {}
        if states:
            params["states"] = states

        try:
            response = await self._async_request(
                REFERENCE_ENDPOINT,
                params=params,
                extra_headers=headers,
            )

        except (
            NSWFuelApiClientAuthError,
            NSWFuelApiClientConnectionError,
            NSWFuelApiClientError,
        ):
            # Bubble up failures (so HA can handle reauth flow, retry flow)
            raise

        except Exception as err:
            # Catch unexpected parsing or logic issues
            msg = f"Unexpected failure fetching reference data: {err}"
            raise NSWFuelApiClientError(msg) from err

        if not response:
            msg = "Empty response from reference data endpoint"
            raise NSWFuelApiClientError(msg)

        return GetReferenceDataResponse.deserialize(response)
