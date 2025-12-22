"""Constants for nsw-fuel-api-client."""

from logging import Logger, getLogger

AUTH_URL = "https://api.onegov.nsw.gov.au/oauth/client_credential/accesstoken?grant_type=client_credentials"
BASE_URL = "https://api.onegov.nsw.gov.au"
REFERENCE_ENDPOINT = "/FuelCheckRefData/v2/fuel/lovs"
PRICE_ENDPOINT = "/FuelPriceCheck/v2/fuel/prices/station/{station_code}"
PRICES_ENDPOINT = "/FuelPriceCheck/v2/fuel/prices"
NEARBY_ENDPOINT = "/FuelPriceCheck/v2/fuel/prices/nearby"
REF_DATA_REFRESH_DAYS = 30
DEFAULT_TIMEOUT = 30  # seconds
DEFAULT_STATE = "NSW"
HTTP_UNAUTHORIZED = 401
HTTP_INTERNAL_SERVER_ERROR = 500
HTTP_TIMEOUT_ERROR = 408
HTTP_CLIENT_SERVER_ERROR = 400

