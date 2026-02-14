"""
Order processing and context resolution service for HeavyHaul AI.

Handles order ID extraction from queries, position-based order selection,
and context-aware order switching for conversational flow.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from config.constants import POSITION_DESCRIPTIONS, POSITION_MAPPINGS
from db import get_db
from services.data_filter import filter_order_by_role

logger = logging.getLogger(__name__)


def get_admin_order_id(query: str) -> Optional[int]:
    """Extract an order ID from an admin's natural language query.

    Supports patterns like 'order 2892', '#2892', 'about 2892'.

    Args:
        query: The user's query text.

    Returns:
        The validated order ID, or None if not found.
    """
    patterns = [
        r"order\s+#?(\d{4,})",
        r"#(\d{4,})",
        r"\b(\d{4,})\b",
        r"(?:about|for|id)\s+#?(\d{4,})",
    ]

    db = get_db()
    try:
        for pattern in patterns:
            match = re.search(pattern, query.lower())
            if match:
                order_id = int(match.group(1))
                if db.orders.find_one({"id": order_id}):
                    return order_id
    except Exception as e:
        logger.error("Error extracting admin order ID: %s", e)

    return None


def resolve_order_context(
    query: str,
    current_order_id: Optional[int],
    user_data: Dict[str, Any],
) -> Tuple[bool, List[int], str]:
    """Determine which order the user is asking about.

    Resolves order references from queries like "latest order",
    "second last order", or explicit order IDs. Handles admin,
    driver, and client roles differently.

    Args:
        query: The user's query text.
        current_order_id: Currently active order ID (may be None).
        user_data: User info from get_user_info().

    Returns:
        Tuple of (should_switch, order_ids, explanation).
    """
    try:
        # Admin role: extract order ID from query
        if "admin_info" in user_data:
            order_id = get_admin_order_id(query)
            if order_id:
                return True, [order_id], f"Accessing order {order_id} as admin"
            elif current_order_id:
                return (
                    False,
                    [current_order_id],
                    f"Continuing with current order {current_order_id}",
                )
            return False, [], "Please specify an order ID"

        # Driver/Client role: use order list
        if "driver_info" in user_data:
            order_ids = sorted(
                user_data["driver_info"]["order_ids"], reverse=True
            )
            user_type = "driver"
        elif "client_info" in user_data:
            order_ids = sorted(
                user_data["client_info"]["order_ids"], reverse=True
            )
            user_type = "client"
        else:
            return False, [], "Invalid user data"

        query_lower = query.lower()

        # Check position references ("third last", "latest", etc.)
        for position_text, index in POSITION_MAPPINGS.items():
            if position_text in query_lower:
                if index < len(order_ids):
                    oid = order_ids[index]
                    desc = POSITION_DESCRIPTIONS.get(index, f"{index + 1}th latest")
                    return True, [oid], f"Using {desc} order ({oid}) for {user_type}"
                return (
                    False,
                    [],
                    f"No {position_text} order available for {user_type}",
                )

        # Handle ordinal numbers ("3rd latest", "1st latest")
        ordinal_pattern = re.compile(r"(\d+)(?:st|nd|rd|th)\s+latest")
        ordinal_match = ordinal_pattern.search(query_lower)
        if ordinal_match:
            index = int(ordinal_match.group(1)) - 1
            if index < len(order_ids):
                oid = order_ids[index]
                return (
                    True,
                    [oid],
                    f"Using {ordinal_match.group(0)} order ({oid}) for {user_type}",
                )
            return (
                False,
                [],
                f"No {ordinal_match.group(0)} order available for {user_type}",
            )

        # Handle direct order ID mentions
        numbers = re.findall(r"\b\d+\b", query)
        for num in numbers:
            oid = int(num)
            if oid in order_ids:
                position = order_ids.index(oid)
                desc = POSITION_DESCRIPTIONS.get(position, f"{position + 1}th latest")
                return (
                    True,
                    [oid],
                    f"Using order {oid} ({desc} order) for {user_type}",
                )

        # Continue with current order if set
        if current_order_id is not None:
            return (
                False,
                [current_order_id],
                f"Continuing with current order {current_order_id} for {user_type}",
            )

        # Default to latest order
        if order_ids:
            return (
                True,
                [order_ids[0]],
                f"Using latest order {order_ids[0]} for {user_type}",
            )

        return False, [], f"No orders found for {user_type}"

    except Exception as e:
        logger.error("Error resolving order context: %s", e)
        return False, [], "Error in processing"


def get_order_details(
    order_ids: List[int], role: str
) -> List[Dict[str, Any]]:
    """Fetch and filter order details from the database.

    Args:
        order_ids: List of order IDs to fetch.
        role: User role for data filtering.

    Returns:
        List of filtered order detail dictionaries.
    """
    try:
        db = get_db()
        orders = list(db.orders.find({"id": {"$in": order_ids}}))

        return [
            {
                "Order ID": order["id"],
                "Order Details": filter_order_by_role(order["order"], role),
            }
            for order in orders
        ]
    except Exception as e:
        logger.error("Error getting order details: %s", e)
        return []
