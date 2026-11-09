"""Place search for the origin and destination inputs, backed by TomTom Search."""

import hashlib
import logging
from urllib.parse import quote

import requests
from django.conf import settings
from django.core.cache import cache

from .errors import UpstreamError

logger = logging.getLogger(__name__)

SEARCH_URL = "https://api.tomtom.com/search/2/search"
COUNTRIES = "US,CA,MX"
RESULT_LIMIT = 6
CACHE_SECONDS = 24 * 60 * 60
REQUEST_TIMEOUT_SECONDS = 8


def search_places(query: str) -> list[dict]:
    key = "geocode:" + hashlib.sha256(query.casefold().encode()).hexdigest()
    places = cache.get(key)
    if places is not None:
        return places

    try:
        response = requests.get(
            f"{SEARCH_URL}/{quote(query, safe='')}.json",
            params={
                "key": settings.TOMTOM_API_KEY,
                "typeahead": "true",
                "limit": RESULT_LIMIT,
                "countrySet": COUNTRIES,
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        # Log only the type: the exception text contains the URL and its API key.
        logger.warning("TomTom search failed: %s", type(error).__name__)
        raise UpstreamError("Place search is unavailable. Please try again.") from None

    places = _unique([_to_place(result) for result in response.json()["results"]])
    cache.set(key, places, CACHE_SECONDS)
    return places


def _to_place(result: dict) -> dict:
    address = result["address"]["freeformAddress"]
    name = result.get("poi", {}).get("name")
    return {
        "label": f"{name}, {address}" if name else address,
        "lat": result["position"]["lat"],
        "lon": result["position"]["lon"],
    }


def _unique(places: list[dict]) -> list[dict]:
    """Drop repeated labels, keeping the first (best-ranked) of each."""
    seen: dict[str, dict] = {}
    for place in places:
        seen.setdefault(place["label"], place)
    return list(seen.values())
