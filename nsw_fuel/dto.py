"""NSW Fuel Check API data types."""

from contextlib import suppress
from datetime import datetime
from enum import Enum
from typing import Any, NamedTuple

from .const import DEFAULT_STATE


class Price:
    """Fuel Price by fuel type, by station."""

    def __init__(self, fuel_type: str, price: float,
                 last_updated: datetime | None, price_unit: str | None,
                 station_code: int | None) -> None:
        """Initialize fuel price details."""
        self.fuel_type = fuel_type
        self.price = price
        self.last_updated = last_updated
        self.price_unit = price_unit
        self.station_code = station_code


    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> "Price":
        """Convert API JSON data into a Price object."""
        lastupdated = None

        # Try both date formats (API is inconsistent…)
        with suppress(ValueError):
            lastupdated = datetime.strptime(data["lastupdated"], "%d/%m/%Y %H:%M:%S")  # noqa: DTZ007

        if lastupdated is None:
            with suppress(ValueError):
                lastupdated = datetime.strptime(  # noqa: DTZ007
                    data["lastupdated"], "%Y-%m-%d %H:%M:%S")

        station_code = int(data["stationcode"]) if "stationcode" in data else None

        return Price(
                fuel_type=data["fueltype"],
                price=data["price"],
                last_updated=lastupdated,
                price_unit=data.get("priceunit"),
                station_code=station_code
            )


    def __repr__(self) -> str:
        """Represent object as string."""
        return f"<Price fuel_type={self.fuel_type} price={self.price}>"


class Station:
    """Fuel Station attributes."""

    def __init__(self, ident: str | None,  # noqa: PLR0913
                brand: str, code: int,
                name: str,
                address: str,
                latitude: float,
                longitude: float,
                au_state: str) -> None:
        """Initialise a Station with identifying and location details."""
        self.ident = ident
        self.brand = brand
        self.code = code
        self.name = name
        self.address = address
        self.latitude = latitude
        self.longitude = longitude
        self.au_state = au_state


    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> "Station":
        """Convert station attributes to typed object."""
        return Station(
            ident=data.get("stationid"),
            brand=data["brand"],
            code=int(data["code"]),
            name=data["name"],
            address=data["address"],
            latitude=data["location"]["latitude"],
            longitude=data["location"]["longitude"],
            au_state=data.get("state") or DEFAULT_STATE,
        )


    def __repr__(self) -> str:
        """Represent object as string."""
        return (
            f"<Station ident={self.ident} code={self.code} brand={self.brand} "
            f"{self.name=} {self.latitude=} {self.longitude=} {self.au_state=}>"
        )


class StationPrice(NamedTuple):
    """StationPrice."""

    price: Price
    station: Station


class Period(Enum):
    """Supported time periods used for pricing variance calculations."""

    DAY = "Day"
    MONTH = "Month"
    YEAR = "Year"
    WEEK = "Week"


class Variance:
    """Represent the price variance of a fuel type over a given period."""

    def __init__(self, fuel_type: str, period: Period, price: float) -> None:
        """Initialize a Variance value."""
        self.fuel_type = fuel_type
        self.period = period
        self.price = price


    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> "Variance":
        """Create a Variance instance from API response data."""
        return Variance(
            fuel_type=data["Code"],
            period=Period(data["Period"]),
            price=data["Price"],
        )


    def __repr__(self) -> str:
        """Represent variance instance as string."""
        return(
            f"<Variance fuel_type={self.fuel_type} period={self.period} "
            f"price={self.price}>"
        )


class AveragePrice:
    """Average price by fuel type for a time period."""

    def __init__(self, fuel_type: str, period: Period, price: float,
                 captured: datetime) -> None:
        """Initialize an AveragePrice value."""
        self.fuel_type = fuel_type
        self.period = period
        self.price = price
        self.captured = captured


    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> "AveragePrice":
        """Create an AveragePrice instance from API response data."""
        period = Period(data["Period"])

        captured_raw = data["Captured"]
        if period in [Period.DAY, Period.WEEK, Period.MONTH]:
            captured = datetime.strptime(captured_raw, "%Y-%m-%d")  # noqa: DTZ007
        elif period == Period.YEAR:
            captured = datetime.strptime(captured_raw, "%B %Y")  # noqa: DTZ007
        else:
            captured = captured_raw

        return AveragePrice(
            fuel_type=data["Code"],
            period=period,
            price=data["Price"],
            captured=captured,
        )


    def __repr__(self) -> str:
        """Return average price instance data as string."""
        return (
            f"<AveragePrice fuel_type={self.fuel_type} period={self.period} "
            f"price={self.price} captured={self.captured}>"
        )


class FuelType:
    """Describe a fuel type code and name."""

    def __init__(self, code: str, name: str) -> None:
        """Initialize a FuelType."""
        self.code = code
        self.name = name


    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> "FuelType":
        """Create a FuelType instance from API response data."""
        return FuelType(
            code=data["code"],
            name=data["name"]
        )


class TrendPeriod:
    """Represent a trend-analysis period and its description."""

    def __init__(self, period: str, description: str) -> None:
        """Initialize a TrendPeriod."""
        self.period = period
        self.description = description


    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> "TrendPeriod":
        """Create a TrendPeriod instance from API response data."""
        return TrendPeriod(
            period=data["period"],
            description=data["description"]
        )


class SortField:
    """Represent a sortable field for fuel price lists."""

    def __init__(self, code: str, name: str) -> None:
        """Initialize a SortField."""
        self.code = code
        self.name = name


    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> "SortField":
        """Create a SortField instance from API response data."""
        return SortField(
            code=data["code"],
            name=data["name"]
        )


class GetReferenceDataResponse:
    """Container for reference data returned from the API."""

    def __init__(self, stations: list[Station], brands: list[str],
                 fuel_types: list[FuelType], trend_periods: list[TrendPeriod],
                 sort_fields: list[SortField]) -> None:
        """Initialize a GetReferenceDataResponse object."""
        self.stations = stations
        self.stations = stations
        self.brands = brands
        self.fuel_types = fuel_types
        self.trend_periods = trend_periods
        self.sort_fields = sort_fields


    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> "GetReferenceDataResponse":
        """Convert raw API reference data to typed objects."""
        stations = [Station.deserialize(x) for x in data["stations"]["items"]]
        brands = [x["name"] for x in data["brands"]["items"]]
        fuel_types = [FuelType.deserialize(x) for x in
                      data["fueltypes"]["items"]]
        trend_periods = [TrendPeriod.deserialize(x) for x in
                         data["trendperiods"]["items"]]
        sort_fields = [SortField.deserialize(x) for x in
                       data["sortfields"]["items"]]

        return GetReferenceDataResponse(
            stations=stations,
            brands=brands,
            fuel_types=fuel_types,
            trend_periods=trend_periods,
            sort_fields=sort_fields
        )


    def __repr__(self) -> str:
        """Return a string representation of the reference data response."""
        return (f"<GetReferenceDataResponse stations=<{len(self.stations)} stations>>")


class GetFuelPricesResponse:
    """Container for fuel price data returned from the API."""

    def __init__(self, stations: list[Station], prices: list[Price]) -> None:
        """Initialize a GetFuelPricesResponse object."""
        self.stations = stations
        self.prices = prices


    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> "GetFuelPricesResponse":
        """Convert API fuel prices as string to typed object."""
        stations = [Station.deserialize(x) for x in data["stations"]]
        prices = [Price.deserialize(x) for x in data["prices"]]
        return GetFuelPricesResponse(
            stations=stations,
            prices=prices
        )