"""Constants for nsw-fuel-api-client."""

AUTH_URL = "https://api.onegov.nsw.gov.au/oauth/client_credential/accesstoken?grant_type=client_credentials"
BASE_URL = "https://api.onegov.nsw.gov.au"
DEFAULT_STATE = "NSW"
DEFAULT_TIMEOUT = 30  # seconds
HTTP_CLIENT_SERVER_ERROR = 400
HTTP_INTERNAL_SERVER_ERROR = 500
HTTP_TIMEOUT_ERROR = 408
HTTP_UNAUTHORIZED = 401
NEARBY_ENDPOINT = "/FuelPriceCheck/v2/fuel/prices/nearby"
PRICE_ENDPOINT = "/FuelPriceCheck/v2/fuel/prices/station/{station_code}"
PRICES_ENDPOINT = "/FuelPriceCheck/v2/fuel/prices"
REF_DATA_REFRESH_DAYS = 30
REFERENCE_ENDPOINT = "/FuelCheckRefData/v2/fuel/lovs"

