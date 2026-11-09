"""Weather risk classification, implementing the assessment's risk and load rules.

Boundary decisions (the spec's bands share their edges):

* Wind bands are whole-mph ranges, so a band runs up to the next band's start:
  44.6 mph is still in "35-44".
* Rain and snow bands are upper-inclusive. The table says Low is ``<0.10`` and
  No Travel is ``>1.00``, so 0.10 must be Moderate and 1.00 must be Severe.
  Upper-inclusive is the only reading consistent with both, and it resolves
  the shared edges (0.25 is Moderate, 0.50 is High).
"""

from dataclasses import dataclass
from enum import IntEnum


class RiskLevel(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()


@dataclass(frozen=True)
class Weather:
    wind_mph: float
    rain_in_hr: float
    snow_in_hr: float


@dataclass(frozen=True)
class RiskAssessment:
    level: RiskLevel
    reasons: tuple[str, ...]


WIND_BANDS = (0, 25, 35, 45, 55)
RAIN_BANDS = (0, 0.10, 0.25, 0.50, 1.00)
SNOW_BANDS = (0, 0.5, 1.0, 2.0, 3.0)

LOAD_LIMIT_NO_TRAVEL_LB = 30_000
LOAD_LIMIT_SEVERE_LB = 40_000


def classify_wind(mph: float) -> RiskLevel:
    if mph < 25:
        return RiskLevel.LOW
    if mph < 35:
        return RiskLevel.MODERATE
    if mph < 45:
        return RiskLevel.HIGH
    if mph < 55:
        return RiskLevel.SEVERE
    return RiskLevel.NO_TRAVEL


def classify_rain(in_hr: float) -> RiskLevel:
    if in_hr < 0.10:
        return RiskLevel.LOW
    if in_hr <= 0.25:
        return RiskLevel.MODERATE
    if in_hr <= 0.50:
        return RiskLevel.HIGH
    if in_hr <= 1.00:
        return RiskLevel.SEVERE
    return RiskLevel.NO_TRAVEL


def classify_snow(in_hr: float) -> RiskLevel:
    if in_hr < 0.5:
        return RiskLevel.LOW
    if in_hr <= 1.0:
        return RiskLevel.MODERATE
    if in_hr <= 2.0:
        return RiskLevel.HIGH
    if in_hr <= 3.0:
        return RiskLevel.SEVERE
    return RiskLevel.NO_TRAVEL


def apply_load_rules(wind_level: RiskLevel, load_lb: float) -> RiskLevel:
    """Escalate a wind classification for heavy loads.

    The >=55 mph "No Travel for any load" rule is already covered by
    ``classify_wind``.
    """
    if wind_level is RiskLevel.SEVERE and load_lb > LOAD_LIMIT_NO_TRAVEL_LB:
        return RiskLevel.NO_TRAVEL
    if wind_level is RiskLevel.HIGH and load_lb > LOAD_LIMIT_SEVERE_LB:
        return RiskLevel.SEVERE
    return wind_level


def assess(weather: Weather, load_lb: float) -> RiskAssessment:
    """Return the worst level across wind (after load rules), rain and snow."""
    base_wind = classify_wind(weather.wind_mph)
    wind = apply_load_rules(base_wind, load_lb)
    rain = classify_rain(weather.rain_in_hr)
    snow = classify_snow(weather.snow_in_hr)
    level = max(wind, rain, snow)

    if level is RiskLevel.LOW:
        return RiskAssessment(level, ())

    reasons = []
    if wind is level:
        escalated = " with this load" if wind is not base_wind else ""
        reasons.append(f"Wind {weather.wind_mph:.0f} mph{escalated}")
    if rain is level:
        reasons.append(f"Rain {weather.rain_in_hr:.2f} in/hr")
    if snow is level:
        reasons.append(f"Snow {weather.snow_in_hr:.2f} in/hr")
    return RiskAssessment(level, tuple(reasons))


def heat_score(weather: Weather, load_lb: float) -> int:
    """Heatmap value on a 0-40 scale.

    The tens digit is always the checkpoint risk level. The units digit shows
    how far conditions are through that level's band, so the map has a visible
    gradient even when an entire corridor is Low.
    """
    level = assess(weather, load_lb).level
    if level is RiskLevel.NO_TRAVEL:
        return 40
    fractions = [
        _band_fraction(value, bands)
        for value, bands, classified in (
            (weather.wind_mph, WIND_BANDS, apply_load_rules(classify_wind(weather.wind_mph), load_lb)),
            (weather.rain_in_hr, RAIN_BANDS, classify_rain(weather.rain_in_hr)),
            (weather.snow_in_hr, SNOW_BANDS, classify_snow(weather.snow_in_hr)),
        )
        if classified is level
    ]
    return int(level) * 10 + min(9, int(max(fractions) * 10))


def _band_fraction(value: float, bands: tuple[float, ...]) -> float:
    for lower, upper in zip(bands, bands[1:]):
        if lower <= value < upper:
            return (value - lower) / (upper - lower)
    return 0.0
