"""NSW Fuel Check API data types."""

from contextlib import suppress
from datetime import datetime
from enum import Enum
from typing import Any


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
        """Convert API data into a Price object."""
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

    def __init__(self, id: str | None, brand: str, code: int,  # noqa: PLR0913
            name: str, address: str, latitude: float, longitude: float) -> None:
        """Initialise a Station with identifying and location details."""
        self.id = id
        self.brand = brand
        self.code = code
        self.name = name
        self.address = address
        self.latitude = latitude
        self.longitude = longitude

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> "Station":
        """Convert station attributes to typed object."""
        return Station(
            id=data.get("stationid"),
            brand=data["brand"],
            code=int(data["code"]),
            name=data["name"],
            address=data["address"],
            latitude=data["location"]["latitude"],
            longitude=data["location"]["longitude"],
        )

    def __repr__(self) -> str:
        """Represent object as string."""
        return(
            f"<Station id={self.id} code={self.code} brand={self.brand} "
            f"name={self.name} latitude={self.latitude} longitude={self.longitude}>"
        )

class Period(Enum):
    DAY = "Day"
    MONTH = "Month"
    YEAR = "Year"
    WEEK = "Week"


class Variance:
    def __init__(self, fuel_type: str, period: Period, price: float) -> None:
        self.fuel_type = fuel_type
        self.period = period
        self.price = price

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> "Variance":
        return Variance(
            fuel_type=data["Code"],
            period=Period(data["Period"]),
            price=data["Price"],
        )

    def __repr__(self) -> str:
        """Represent object as string."""
        return(
            f"<Variance fuel_type={self.fuel_type} period={self.period} "
            f"price={self.price}>"
        )

class AveragePrice:
    """Average price by fuel type for a time period."""

    def __init__(self, fuel_type: str, period: Period, price: float,
                 captured: datetime) -> None:
        self.fuel_type = fuel_type
        self.period = period
        self.price = price
        self.captured = captured

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> "AveragePrice":
        """Convert string to typed object."""
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
        """Return instance data as string."""
        return (f"<AveragePrice fuel_type={self.fuel_type} period={self.period} price={self.price} "
                f"captured={self.captured}>")


class FuelType(object):
    def __init__(self, code: str, name: str) -> None:
        self.code = code
        self.name = name

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> "FuelType":
        return FuelType(
            code=data["code"],
            name=data["name"]
        )


class TrendPeriod:
    def __init__(self, period: str, description: str) -> None:
        self.period = period
        self.description = description

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> "TrendPeriod":
        return TrendPeriod(
            period=data["period"],
            description=data["description"]
        )


class SortField:
    def __init__(self, code: str, name: str) -> None:
        self.code = code
        self.name = name

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> "SortField":
        return SortField(
            code=data["code"],
            name=data["name"]
        )


class GetReferenceDataResponse:
    def __init__(self, stations: list[Station], brands: list[str],
                 fuel_types: list[FuelType], trend_periods: list[TrendPeriod],
                 sort_fields: list[SortField]) -> None:
        self.stations = stations
        self.brands = brands
        self.fuel_types = fuel_types
        self.trend_periods = trend_periods
        self.sort_fields = sort_fields

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> "GetReferenceDataResponse":
        """Convert raw reference data to typed objects."""
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
        """Return instance as string."""
        return (f"<GetReferenceDataResponse stations=<{len(self.stations)} stations>>")


class GetFuelPricesResponse:
    def __init__(self, stations: list[Station], prices: list[Price]) -> None:
        self.stations = stations
        self.prices = prices

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> "GetFuelPricesResponse":
        """Convert fuel prices as string to typed object."""
        stations = [Station.deserialize(x) for x in data["stations"]]
        prices = [Price.deserialize(x) for x in data["prices"]]
        return GetFuelPricesResponse(
            stations=stations,
            prices=prices
        )
