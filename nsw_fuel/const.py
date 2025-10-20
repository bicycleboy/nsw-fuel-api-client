"""Constants for nsw-fuel-api-client."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

AUTH_URL = "https://api.onegov.nsw.gov.au/oauth/client_credential/accesstoken?grant_type=client_credentials"
BASE_URL = "https://api.onegov.nsw.gov.au"
REFERENCE_ENDPOINT = "/FuelCheckRefData/v2/fuel/lovs"
PRICE_ENDPOINT = "/FuelPriceCheck/v2/fuel/prices/station/{station_code}"
TRENDS_ENDPOINT = "/FuelPriceCheck/v2/fuel/prices/trends"
PRICES_ENDPOINT = "/FuelPriceCheck/v2/fuel/prices"
NEARBY_ENDPOINT = "/FuelPriceCheck/v2/fuel/prices/nearby"
REF_DATA_REFRESH_DAYS = 30
