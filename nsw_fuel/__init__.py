"""NSW Fuel Check API."""
from .client import FuelCheckClient, NSWFuelApiClientError
from .dto import (
    AveragePrice,
    FuelType,
    GetFuelPricesResponse,
    GetReferenceDataResponse,
    Period,
    Price,
    SortField,
    Station,
    TrendPeriod,
    Variance,
)

__all__ = [
    "AveragePrice",
    "FuelCheckClient",
    "FuelType",
    "GetFuelPricesResponse",
    "GetReferenceDataResponse",
    "NSWFuelApiClientError",
    "Period",
    "Price",
    "SortField",
    "Station",
    "TrendPeriod",
    "Variance",
]
__version__ = "0.0.0-dev"
