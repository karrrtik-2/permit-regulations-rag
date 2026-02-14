from typing import Any, Dict, FrozenSet, List, Union
from config.constants import (
    ADMIN_EXCLUDED_FIELDS,
    COMMON_EXCLUDED_FIELDS,
    META_EXCLUDED_FIELDS,
)


def _filter_recursive(
    data: Any,
    excluded: FrozenSet[str],
    meta_excluded: FrozenSet[str],
) -> Any:
    """Recursively filter data by removing excluded fields.

    Args:
        data: Input data structure.
        excluded: Top-level fields to exclude.
        meta_excluded: Meta/internal fields to always exclude.

    Returns:
        Filtered data structure.
    """
    if isinstance(data, dict):
        return {
            k: _filter_recursive(v, excluded, meta_excluded)
            for k, v in data.items()
            if k not in excluded and k not in meta_excluded
        }
    elif isinstance(data, list):
        return [_filter_recursive(item, excluded, meta_excluded) for item in data]
    return data


def filter_order_for_driver(order_data: Dict[str, Any]) -> Dict[str, Any]:
    """Filter order data for driver role.

    Removes company attributes, transactions, logs, meta data,
    and internal tracking fields not relevant to drivers.

    Args:
        order_data: Raw order data dictionary.

    Returns:
        Filtered order data for driver consumption.
    """
    return _filter_recursive(order_data, COMMON_EXCLUDED_FIELDS, META_EXCLUDED_FIELDS)


def filter_order_for_client(order_data: Dict[str, Any]) -> Dict[str, Any]:
    """Filter order data for client role.

    Removes company attributes, transactions, logs, meta data,
    and internal tracking fields not relevant to clients.

    Args:
        order_data: Raw order data dictionary.

    Returns:
        Filtered order data for client consumption.
    """
    return _filter_recursive(order_data, COMMON_EXCLUDED_FIELDS, META_EXCLUDED_FIELDS)


def filter_order_for_admin(order_data: Dict[str, Any]) -> Dict[str, Any]:
    """Filter order data for admin role.

    Admins get more data than drivers/clients but still have
    some internal fields excluded.

    Args:
        order_data: Raw order data dictionary.

    Returns:
        Filtered order data for admin consumption.
    """
    return _filter_recursive(order_data, ADMIN_EXCLUDED_FIELDS, META_EXCLUDED_FIELDS)


def filter_order_by_role(order_data: Dict[str, Any], role: str) -> Dict[str, Any]:
    """Filter order data based on user role.

    Args:
        order_data: Raw order data dictionary.
        role: User role ('driver', 'client', or 'admin').

    Returns:
        Filtered order data appropriate for the given role.

    Raises:
        ValueError: If role is not recognized.
    """
    filters = {
        "driver": filter_order_for_driver,
        "client": filter_order_for_client,
        "admin": filter_order_for_admin,
    }

    filter_func = filters.get(role)
    if filter_func is None:
        raise ValueError(f"Unknown role: {role}. Expected 'driver', 'client', or 'admin'.")

    return filter_func(order_data)
