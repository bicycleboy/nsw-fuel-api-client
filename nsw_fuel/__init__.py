"""NSW Fuel Check API."""

from .client import (
    AustralianState,
    NSWFuelApiClient,
    NSWFuelApiClientAuthError,
    NSWFuelApiClientConnectionError,
    NSWFuelApiClientError,
)
from .dto import (
    GetFuelPricesResponse,
    GetReferenceDataResponse,
    Price,
    Station,
)

__all__ = [
    "AustralianState",
    "GetFuelPricesResponse",
    "GetReferenceDataResponse",
    "NSWFuelApiClient",
    "NSWFuelApiClientAuthError",
    "NSWFuelApiClientConnectionError",
    "NSWFuelApiClientError",
    "Price",
    "Station",
]
__version__ = "2.0.0-dev"
