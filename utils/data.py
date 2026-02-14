"""
Data manipulation utilities for HeavyHaul AI.

Functions for cleaning, filtering, and transforming order data structures.
"""

from typing import Any, Dict, List, Optional, Union


def remove_null_fields(data: Any) -> Any:
    """Recursively remove None values from nested data structures.

    Args:
        data: Input data (dict, list, or scalar).

    Returns:
        Data with None values removed.
    """
    if isinstance(data, dict):
        return {k: remove_null_fields(v) for k, v in data.items() if v is not None}
    elif isinstance(data, list):
        return [remove_null_fields(item) for item in data if item is not None]
    return data


def remove_deleted_permits(route_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter out routes with 'Delete' permit status.

    Args:
        route_data: List of route dictionaries.

    Returns:
        Filtered list excluding deleted permits.
    """
    return [
        route for route in route_data
        if route.get("permit_status") != "Delete"
    ]
