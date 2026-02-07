"""NSW Fuel Check API, main API interface."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from aiohttp import (
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
    HTTP_CLIENT_SERVER_ERROR,
    HTTP_INTERNAL_SERVER_ERROR,
    HTTP_TIMEOUT_ERROR,
    HTTP_UNAUTHORIZED,
    NEARBY_ENDPOINT,
    PRICE_ENDPOINT,
    PRICES_ENDPOINT,
    REFERENCE_ENDPOINT,
)
from .dto import (
    GetFuelPricesResponse,
    GetReferenceDataResponse,
    Price,
    Station,
    StationPrice,
)

_LOGGER = logging.getLogger(__name__)


class NSWFuelApiClientError(Exception):
    """Base class for all NSW Fuel API errors."""


class NSWFuelApiClientAuthError(NSWFuelApiClientError):
    """Authentication failure (invalid or expired credentials)."""


class NSWFuelApiClientConnectionError(NSWFuelApiClientError):
    """Connection or server availability issue."""


class NSWFuelApiClient:
    """Main API client for NSW FuelCheck."""

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
        Get or refresh OAuth2 token from the NSW Fuel Check API.

        Raises:
            NSWFuelApiClientAuthError: If authentication fails (401).
            NSWFuelApiClientError: For all other token fetch or parse errors.

        """
        now = time.time()

        if not self._token or now > (self._token_expiry - 60):
            _LOGGER.debug("Refreshing NSW Fuel API token")

            params = {"grant_type": "client_credentials"}
            auth_str = f"{self._client_id}:{self._client_secret}"
            auth_b64 = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
            headers = {
                "Accept": "application/json",
                "Authorization": f"Basic {auth_b64}",
            }

            try:
                async with self._session.get(
                    AUTH_URL,
                    params=params,
                    headers=headers) as response:
                    # Raise for non-2xx HTTP status codes
                    response.raise_for_status()

                    # Deserialize JSON response
                    try:
                        if "application/json" in response.content_type:
                            result = await response.json()
                        else:
                            text = await response.text()
                            _LOGGER.warning(
                                "Expected application/json, got %s",
                                response.content_type)
                            result = json.loads(text)
                    except (json.JSONDecodeError, ValueError) as err:
                        msg = "Failed to parse token response JSON"
                        _LOGGER.debug("Unexpected eror: %s:", msg)
                        raise NSWFuelApiClientError(msg) from err


            except ClientResponseError as err:
                if err.status == HTTP_UNAUTHORIZED:
                    msg = "Invalid NSW Fuel Check API credentials"
                    # Return specific auth error to applicatioin eg home assisant
                    # so the user can reenter credenentials
                    _LOGGER.debug(msg)
                    raise NSWFuelApiClientAuthError(msg) from err
                msg = f"Token request failed with status {err.status}: {err.message}"
                _LOGGER.debug(msg)
                raise NSWFuelApiClientError(msg) from err

            except Exception as err:
                msg = f"Unexpected error fetching token: {err}"
                _LOGGER.debug("%s", msg)
                raise NSWFuelApiClientError(msg) from err

            # No errors, validate token
            access_token = result.get("access_token")
            if not access_token:
                msg = "No access token in NSW Fuel Check token response"
                _LOGGER.debug("Unexpeted errror: %s", msg)
                raise NSWFuelApiClientError(msg)

            expires_in = int(result.get("expires_in", 3600))
            self._token = access_token
            self._token_expiry = now + expires_in

        return self._token


    async def _async_request(  # noqa: PLR0915
        self,
        path: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> Any:
        """
        Process HTTP requests (except auth), supports GET or POST to the Fuel Check API.

        Raises:
            NSWFuelApiClientAuthError: If authentication fails.
            NSWFuelApiClientConnectionError: If network or server issues occur.
            NSWFuelApiClientError: For all other API or data validation errors.

        """

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
            status: int,
            data: Any,
            response: ClientResponse,
            attempt: int,
            max_retries: int,
        ) -> bool:
            """
            Process HTTP errors and determine if retry is needed.

            If the Oauth token is invalid (even though expiry checked), try a new one.
            The NSW Fuel API appears returns 408 when busy, so retry.

            Returns:
                True if caller should retry the request.
                Raises appropriate exceptions otherwise.

            """
            details = self._extract_error_details(data)

            if status == HTTP_UNAUTHORIZED:
                if attempt < max_retries:
                    # Clear token to force refresh and retry
                    self._token = None
                    return True
                msg = "Authentication failed during request."
                _LOGGER.debug("HTTP error: %s", details)
                raise NSWFuelApiClientAuthError(
                    details or msg
                )

            if status == HTTP_TIMEOUT_ERROR:
                if attempt < max_retries:
                    return True
                msg = "Request timed out after retry."
                _LOGGER.debug("HTTP error: %s", details)
                raise NSWFuelApiClientConnectionError(
                    details or msg
                )

            # Server errors (5xx)
            if status >= HTTP_INTERNAL_SERVER_ERROR:
                _LOGGER.debug("Server error: (%s): %s", status, response.reason)
                raise NSWFuelApiClientConnectionError(
                    details or f"Server error {status}: {response.reason}"
                )

            # Client errors (4xx but not handled above)
            if status >= HTTP_CLIENT_SERVER_ERROR:
                _LOGGER.debug("HTTP error: (%s): %s", status, response.reason)
                raise NSWFuelApiClientError(
                    details or f"HTTP error {status}: {response.reason}"
                )

            # If status is 2xx or 3xx, no error: no retry needed
            return False

        max_retries = 1
        attempt = 0

        while attempt <= max_retries:
            token = await self._async_get_token()
            if not token:
                msg = "No access token available for NSW Fuel API request"
                raise NSWFuelApiClientError(
                    msg
                )

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

                    should_retry = await _handle_http_error(
                        status, data, response, attempt, max_retries
                    )
                    if should_retry:
                        attempt += 1
                        _LOGGER.debug("Retrying after %d...", status)
                        await asyncio.sleep(0.5)
                        continue

                    return data

            except (NSWFuelApiClientAuthError,
                    NSWFuelApiClientConnectionError,
                    NSWFuelApiClientError) as err:
                # Preserve specific error types and messages
                _LOGGER.debug(
                    "API error from NSW Fuel Check API "
                    "url=%s params=%s error=%s",
                    url,
                    params,
                    err,
                    exc_info=True,
                )
                raise

            except Exception as err:
                # Wrap any other unexpected exceptions in a generic API error
                _LOGGER.debug(
                    "Unexpeced error from NSW Fuel Check API "
                    "url=%s params=%s error=%s",
                    url,
                    params,
                    err,
                    exc_info=True,
                )
                raise NSWFuelApiClientError(str(err)) from err

        # Just in case we exit loop without returning or raising
        msg = "Failed to perform http request"
        raise NSWFuelApiClientError(msg)


    async def get_fuel_prices(self) -> GetFuelPricesResponse:
        """
        Fetch all fuel prices.

        Raises:
            NSWFuelApiClientAuthError: If authentication fails.
            NSWFuelApiClientConnectionError: If network or server issues occur.
            NSWFuelApiClientError: For all other API or data validation errors.

        TODO: Accept state as parameter, API defaults to NSW only

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
            raise

        except Exception as err:
            msg = "Unexpected error fetching fuel prices:"
            _LOGGER.debug("%s (%s) - %s", msg, type(err), err)
            raise NSWFuelApiClientError(msg, err) from err

        if not response:
            msg = "No data returned from NSW Fuel API"
            _LOGGER.debug("%s", msg)
            raise NSWFuelApiClientError(msg)

        # Validate structure
        if "prices" not in response or "stations" not in response:
            msg = "Malformed response: missing required fields"
            _LOGGER.debug("%s", msg)
            raise NSWFuelApiClientError(msg)

        return GetFuelPricesResponse.deserialize(response)


    async def get_fuel_prices_for_station(
        self,
        station_code: str,
        state: str | None = None,
    ) -> list[Price]:
        """
        Fetch the fuel prices for a specific fuel station.

        Raises:
            NSWFuelApiClientAuthError: If authentication fails.
            NSWFuelApiClientConnectionError: If network or server issues occur.
            NSWFuelApiClientError: For all other API or data validation errors.

        """
        params = {"state": state} if state is not None else None

        try:
            response: dict[str, Any] = await self._async_request(
                PRICE_ENDPOINT.format(station_code=station_code),
                params=params,
            )

        except (
            NSWFuelApiClientAuthError,
            NSWFuelApiClientConnectionError,
            NSWFuelApiClientError,
        ):
            # Application, e.g. HA, needs to handle reauth, retry, other errors
            raise

        except Exception as err:
            # Catch unexpected parsing or logic issues
            msg = f"Unexpected failure getting station prices for {station_code}: {err}"
            _LOGGER.debug(msg)
            raise NSWFuelApiClientError(msg) from err

        # Validate response structure
        if not response or "prices" not in response:
            msg = f"Malformed or empty response for station {station_code}"
            _LOGGER.debug(msg)
            raise NSWFuelApiClientError(msg)

        prices_data = response.get("prices")
        if not prices_data:
            msg = f"No price data found for station {station_code}"
            _LOGGER.debug(msg)
            raise NSWFuelApiClientError(msg)

        _LOGGER.debug(
            "get_fuel_prices_for_station fetched %d prices for station %s",
            len(prices_data),
            station_code,
        )

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
        Fetch all fuel prices within the specified radius.

        Args:
            See also API definition at api.nsw.gov.au/Product/Index/22
            latitude: Latitude of the centre point.
            longitude: Longitude of the centre point.
            radius: Radius in kilometers to search.
            fuel_type: Fuel type code (e.g., 'U91', 'E10').
            brands: Optional list of brand names to filter.
            named_location: Suburb or postcode
            sort_by: price or distance
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
                "latitude": str(latitude),
                "longitude": str(longitude),
                "radius": str(radius),
                "sortby": sort_by,
                "sortascending": str(sort_ascending).lower(),
            }

            _LOGGER.debug("get_fuel_prices_within_radius payload=%s", payload)

            response: dict[str, Any] = await self._async_request(
                path=NEARBY_ENDPOINT,
                params=None,
                method="POST",
                json_body=payload,
                extra_headers={"Content-Type": "application/json"},
            )

        except (
            NSWFuelApiClientAuthError,
            NSWFuelApiClientConnectionError,
            NSWFuelApiClientError,
        ):
            # Application, e.g. HA, needs to handle reauth, retry, other errors
            raise

        except Exception as err:
            msg = (
                f"Unexpected error fetching nearby prices for "
                f"({latitude}, {longitude}): {err}"
            )
            _LOGGER.debug(msg)
            raise NSWFuelApiClientError(msg) from err

        # Validate structure
        if not response or "stations" not in response or "prices" not in response:
            msg = f"Malformed or empty response for location ({latitude}, {longitude})"
            _LOGGER.debug(msg)
            raise NSWFuelApiClientError(msg)

        stations_data = response.get("stations")
        prices_data = response.get("prices")
        if not stations_data or not prices_data:
            msg = f"No stations/prices found for location ({latitude}, {longitude})"
            _LOGGER.warning(msg)
            raise NSWFuelApiClientError(msg)

        stations: dict[int, Station] = {
            int(station["code"]): Station.deserialize(station)
            for station in stations_data
        }

        # Deserialize prices JSON and attach stations to create StationPrice objects
        station_prices: list[StationPrice] = []
        for serialized_price in prices_data:
            try:
                price = Price.deserialize(serialized_price)
                if price.station_code is not None:
                    station = stations.get(price.station_code)
                    if station:
                        station_prices.append(
                            StationPrice(price=price, station=station)
                        )
            except (KeyError, TypeError, ValueError) as parse_err:
                _LOGGER.debug("Skipping malformed price entry: %s", parse_err)

        if _LOGGER.isEnabledFor(logging.DEBUG):
            station_names = ", ".join(sp.station.name for sp in station_prices)
            _LOGGER.debug(
                "get_fuel_prices_within_radius returned %d nearby station prices for"
                " lat=%s lon=%s: %s",
                len(station_prices),
                latitude,
                longitude,
                station_names,
            )

        return station_prices


    async def get_reference_data(
        self,
        modified_since: datetime | None = None,
        states: list[str] | None = None,
    ) -> GetReferenceDataResponse:
        """
        Fetch API reference data.

        Params:
            modified_since: Optional datetime to fetch only data modified since this
                timestamp. If None, all reference data will be returned.
            states: Optional list of state abbreviations to filter results.

        Raises:
            NSWFuelApiClientAuthError: If authentication fails.
            NSWFuelApiClientConnectionError: If a network or transport error occurs.
            NSWFuelApiClientError: For all other unexpected API or parsing errors.

        Returns:
            Deserialized GetReferenceDataResponse object.

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
            raise

        except Exception as err:
            msg = f"Unexpected failure fetching reference data: {err}"
            raise NSWFuelApiClientError(msg) from err

        if not response:
            msg = "Empty response from reference data endpoint"
            raise NSWFuelApiClientError(msg)

        return GetReferenceDataResponse.deserialize(response)
