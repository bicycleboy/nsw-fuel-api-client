from __future__ import annotations

import base64
import json
import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional, NamedTuple, Any

from .dto import (
    Price,
    Station,
    Variance,
    AveragePrice,
    GetReferenceDataResponse,
    GetFuelPricesResponse,
)

from .const import (
    AUTH_URL,
    BASE_URL,
    DEFAULT_TIMEOUT,
    HTTP_UNAUTHORIZED,
    HTTP_INTERNAL_SERVER_ERROR,
    LOGGER,
    NEARBY_ENDPOINT,
    PRICE_ENDPOINT,
    PRICES_ENDPOINT,
    REFERENCE_ENDPOINT,
)

from aiohttp import (
    ClientConnectionError,
    ClientError,
    ClientResponseError,
    ClientSession,
    ClientTimeout,
)

UTC = timezone.utc


PriceTrends = NamedTuple(
    "PriceTrends",
    [("variances", List[Variance]), ("average_prices", List[AveragePrice])],
)

StationPrice = NamedTuple("StationPrice", [("price", Price), ("station", Station)])


class NSWFuelApiClientError(Exception):
    """Base class for all NSW Fuel API errors."""


class NSWFuelApiClientAuthError(NSWFuelApiClientError):
    """Authentication failure (invalid or expired credentials)."""


class NSWFuelApiClientConnectionError(NSWFuelApiClientError):
    """Connection or server availability issue."""


class FuelCheckClient:
    """
    API client for NSW FuelCheck.
    """

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
    def _extract_error_details(data: Any) -> Optional[str]:
        """Extract readable error details message from API response data."""
        if not isinstance(data, dict):
            return None

        ed = data.get("errorDetails")
        if isinstance(ed, list) and ed:
            return ed[0].get("description") or ed[0].get("message")
        elif isinstance(ed, dict):
            return ed.get("description") or ed.get("message")
        return None

    async def _async_get_token(self) -> str | None:
        """
        Get or refresh OAuth2 token from the NSW Fuel API.
        Raises:
            NSWFuelApiClientAuthError: If authentication fails.
            NSWFuelApiClientError: For all other token fetch errors.
        """
        LOGGER.debug("_async_get_token called")
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
                    LOGGER.debug("JSON decode error caught here")  # <-- add this temporarily
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

    async def _async_request(
        self,
        path: str,
        method: str = "GET",
        params: Optional[dict[str, Any]] = None,
        json_body: Optional[dict[str, Any]] = None,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> Any:
        """
        Perform an authorized HTTP request (GET or POST) to the NSW Fuel API.
        Raises:
        NSWFuelApiClientAuthError: If authentication fails.
        NSWFuelApiClientConnectionError: If network or server issues occur.
        NSWFuelApiClientError: For all other API or data validation errors.
        """

        token = await self._async_get_token()

        if not token:
            raise NSWFuelApiClientError(
                "No access token available for NSW Fuel API request"
            )

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
                f"{value[:6]}...{value[-4:]}"
                if key == "Authorization" and isinstance(value, str)
                else "REDACTED"
                if key == "apikey"
                else value
            )
            for key, value in headers.items()
        }
        LOGGER.debug(
            "_async_request requesting %s with params=%s, headers=%s",
            url,
            params,
            redacted_headers,
        )

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

                try:
                    data = await response.json(encoding="utf-8", content_type=None)
                except Exception:  # noqa: BLE001
                    data = await response.text()

                # Avoid logging large reference data
                if path != REFERENCE_ENDPOINT:
                    LOGGER.debug("API Response %s: %s", status, data)
                else:
                    LOGGER.debug("API Response %s", status)

                # Handle 401: token just expired, refresh token and retry once (TODO: consider just returning None and AuthError)
                if status == HTTP_UNAUTHORIZED:
                    LOGGER.warning("401 Unauthorized, refreshing token...")
                    self._token = None
                    token = await self._async_get_token()
                    if not token:
                        raise NSWFuelApiClientAuthError(
                            "Failed to refresh token after 401"
                        )

                    headers["Authorization"] = f"Bearer {token}"
                    async with self._session.request(
                        method.upper(),
                        url,
                        headers=headers,
                        params=params,
                        json=json_body,
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

                # Handle errors by extracting error details from response JSON before raising
                if status >= 400:
                    error_details_msg = self._extract_error_details(data)

                    if status == HTTP_UNAUTHORIZED:
                        raise NSWFuelApiClientAuthError(
                            error_details_msg or "Authentication failed during request"
                        )
                    elif status >= HTTP_INTERNAL_SERVER_ERROR:
                        raise NSWFuelApiClientConnectionError(
                            error_details_msg
                            or f"Server error {status}: {response.reason}"
                        )
                    else:
                        raise NSWFuelApiClientError(
                            error_details_msg
                            or f"HTTP error {status}: {response.reason}"
                        )

                # No error, return the data
                return data

        except ClientResponseError as err:
            # Try to parse error details from JSON response body
            error_details_msg = None
            try:
                # We can get the response content from err.response
                if err.response is not None:
                    error_json = await err.response.json(content_type=None)
                    error_details_msg = self._extract_error_details(error_json)
            except Exception:
                # If parsing JSON fails, just ignore and fallback
                pass

            if err.status == HTTP_UNAUTHORIZED:
                raise NSWFuelApiClientAuthError(
                    "Authentication failed during request"
                ) from err
            elif err.status >= HTTP_INTERNAL_SERVER_ERROR:
                raise NSWFuelApiClientConnectionError(
                    f"Server error {err.status}: {err.message}"
                ) from err
            raise NSWFuelApiClientError(
                f"HTTP error {err.status}: {err.message}"
            ) from err

        except ClientError as err:
            raise NSWFuelApiClientError(f"Connection error: {err}") from err

        except NSWFuelApiClientError:
            # Pass through custom exceptions such as from inner try untouched
            raise

        except Exception as err:
            raise NSWFuelApiClientError(f"{err}") from err

    async def get_fuel_prices(self) -> GetFuelPricesResponse:
        """Fetch all NSW fuel prices.

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

            if not response:
                raise NSWFuelApiClientError("No data returned from NSW Fuel API")

            # Validate structure
            if "prices" not in response or "stations" not in response:
                raise NSWFuelApiClientError(
                    "Malformed response: missing required fields"
                )

            return GetFuelPricesResponse.deserialize(response)

        except NSWFuelApiClientAuthError:
            # Pass through unchanged so HA can handle login issues distinctly
            raise

        except NSWFuelApiClientConnectionError:
            # Connection or timeout problems so HA can retry
            raise

        except NSWFuelApiClientError:
            raise

        except Exception as err:
            LOGGER.debug("Caught unexpected Exception: %s - %s", type(err), err)
            raise NSWFuelApiClientError(
                "Unexpected failure fetching fuel prices: %s", err
            ) from err

    async def get_fuel_prices_for_station(
        self,
        station_code: str,
    ) -> List[Price]:
        """Fetch the fuel prices for a specific fuel station asynchronously.

        Raises:
            NSWFuelApiClientAuthError: If authentication fails.
            NSWFuelApiClientConnectionError: If network or server issues occur.
            NSWFuelApiClientError: For all other API or data validation errors.
        """

        try:
            response: dict[str, Any] = await self._async_request(
                PRICE_ENDPOINT.format(station_code=station_code)
            )

            # Validate response structure
            if not response or "prices" not in response:
                raise NSWFuelApiClientError(
                    f"Malformed or empty response for station {station_code}"
                )

            prices_data = response.get("prices")
            if not prices_data:
                raise NSWFuelApiClientError(
                    f"No price data found for station {station_code}"
                )

            # Deserialize prices
            return [Price.deserialize(p) for p in prices_data]

        except NSWFuelApiClientAuthError:
            # Bubble up auth failures (so HA can handle reauth flow)
            raise

        except NSWFuelApiClientConnectionError:
            # Let HA treat this as an unavailable entity
            raise

        except NSWFuelApiClientError:
            raise

        except Exception as err:
            # Catch unexpected parsing or logic issues
            raise NSWFuelApiClientError(
                f"Unexpected failure fetching station prices for {station_code}: {err}"
            ) from err

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

            # Validate structure
            if not response or "stations" not in response or "prices" not in response:
                raise NSWFuelApiClientError(
                    f"Malformed or empty response for location ({latitude}, {longitude})"
                )

            stations_data = response.get("stations")
            prices_data = response.get("prices")
            if not stations_data or not prices_data:
                raise NSWFuelApiClientError(
                    f"No stations or prices found for location ({latitude}, {longitude})"
                )

            # Deserialize stations
            stations: dict[str, Station] = {
                station["code"]: Station.deserialize(station)
                for station in stations_data
            }

            # Deserialize prices and attach stations
            station_prices: List[StationPrice] = []
            for serialized_price in prices_data:
                try:
                    price = Price.deserialize(serialized_price)
                    station_obj = stations.get(price.station_code)
                    if station_obj:
                        station_prices.append(
                            StationPrice(price=price, station=station_obj)
                        )
                except Exception as parse_err:
                    LOGGER.warning("Skipping malformed price entry: %s", parse_err)

            LOGGER.debug(
                "Deserialized %d nearby station prices for lat=%s lon=%s",
                len(station_prices),
                latitude,
                longitude,
            )

            return station_prices

        except NSWFuelApiClientAuthError:
            raise

        except NSWFuelApiClientConnectionError:
            raise

        except NSWFuelApiClientError:
            raise

        except Exception as err:
            raise NSWFuelApiClientError(
                f"Unexpected error fetching nearby prices for "
                f"({latitude}, {longitude}): {err}"
            ) from err

    async def get_reference_data(
        self,
        modified_since: Optional[datetime] = None,
        states: Optional[list[str]] = None,
    ) -> GetReferenceDataResponse:
        """
        Fetch API reference data.

        :param modified_since: Optional datetime to fetch only data modified since this timestamp.
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

            if not response:
                raise NSWFuelApiClientError(
                    "Empty response from reference data endpoint"
                )

            return GetReferenceDataResponse.deserialize(response)

        except NSWFuelApiClientAuthError:
            # Bubble up auth failures (so HA can handle reauth flow)
            raise

        except NSWFuelApiClientConnectionError:
            # Let HA treat this as an unavailable entity
            raise

        except NSWFuelApiClientError:
            raise

        except Exception as err:
            # Catch unexpected parsing or logic issues
            raise NSWFuelApiClientError(
                f"Unexpected failure fetching reference data: {err}"
            ) from err
