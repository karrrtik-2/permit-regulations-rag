"""
Location and weather services for HeavyHaul AI.

Provides geolocation and weather information using
IP-based geocoding and the OpenWeatherMap API.
"""

import logging
from typing import Any, Dict, Optional

import geocoder
import requests
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder

from config.settings import settings

logger = logging.getLogger(__name__)


def get_location() -> Optional[Dict[str, Any]]:
    """Get the current user location via IP geolocation.

    Returns:
        Dictionary with latitude, longitude, city, state, country,
        formatted address, and timezone. None on failure.
    """
    try:
        g = geocoder.ip("me")
        if not g.ok:
            return None

        geolocator = Nominatim(user_agent="heavyhaul-ai-assistant")
        location = geolocator.reverse(f"{g.lat}, {g.lng}")
        if location is None:
            return None

        address = location.raw.get("address", {})
        tf = TimezoneFinder()

        return {
            "latitude": g.lat,
            "longitude": g.lng,
            "city": address.get("city"),
            "state": address.get("state"),
            "country": address.get("country"),
            "formatted_address": location.address,
            "timezone": tf.timezone_at(lat=g.lat, lng=g.lng),
        }
    except Exception as e:
        logger.error("Error getting location: %s", e)
        return None


def get_location_string() -> str:
    """Get a human-readable location string.

    Returns:
        Formatted location string or error message.
    """
    location_data = get_location()
    if location_data:
        return (
            f"You are in {location_data['city']}, "
            f"{location_data['state']}, {location_data['country']}."
        )
    return "I'm sorry, I couldn't determine your location."


def get_weather() -> str:
    """Get weather for the current location.

    Returns:
        Formatted weather string or error message.
    """
    location = get_location()
    if not location:
        return "Unable to determine location for weather information."

    return _fetch_weather(
        lat=location["latitude"],
        lon=location["longitude"],
        city_name=location.get("city", "your location"),
    )


def get_weather_by_city(city_name: str) -> str:
    """Get weather for a specific city.

    Args:
        city_name: Name of the city to look up.

    Returns:
        Formatted weather string or error message.
    """
    try:
        url = (
            f"{settings.weather.base_url}"
            f"?q={city_name}"
            f"&appid={settings.weather.api_key}"
            f"&units={settings.weather.units}"
        )
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            return f"Unable to fetch weather information for {city_name}."

        return _format_weather(response.json(), city_name)

    except Exception as e:
        logger.error("Error getting weather for %s: %s", city_name, e)
        return f"Sorry, I encountered an error while fetching weather for {city_name}."


def _fetch_weather(
    lat: float = 0,
    lon: float = 0,
    city_name: str = "",
) -> str:
    """Internal: Fetch weather data from the API.

    Args:
        lat: Latitude coordinate.
        lon: Longitude coordinate.
        city_name: Display name for the city.

    Returns:
        Formatted weather string.
    """
    try:
        url = (
            f"{settings.weather.base_url}"
            f"?lat={lat}&lon={lon}"
            f"&appid={settings.weather.api_key}"
            f"&units={settings.weather.units}"
        )
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            return "Unable to fetch weather information."

        return _format_weather(response.json(), city_name)

    except Exception as e:
        logger.error("Error fetching weather: %s", e)
        return "Sorry, I encountered an error while fetching weather."


def _format_weather(data: Dict[str, Any], city_name: str) -> str:
    """Format raw weather API response into a readable string.

    Args:
        data: Raw weather JSON from OpenWeatherMap.
        city_name: Display name for the location.

    Returns:
        Formatted weather description.
    """
    temperature = round(data["main"]["temp"])
    feels_like = round(data["main"]["feels_like"])
    humidity = data["main"]["humidity"]
    description = data["weather"][0]["description"]

    return (
        f"The current weather in {city_name} is {description}. "
        f"The temperature is {temperature}°C, feels like {feels_like}°C, "
        f"with {humidity}% humidity."
    )
