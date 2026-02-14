"""
Order caching service for HeavyHaul AI.

Provides file-based caching of order details to reduce repeated
database queries for the same order data.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class OrderCache:
    """File-based order cache with in-memory current order tracking.

    Caches order details as JSON files organized by order ID and role,
    while maintaining the currently active order in memory.

    Attributes:
        current_order_id: The currently active order ID.
        current_details: The details of the current order.
        explanation: Description of why this order was selected.
        current_role: The role of the current user.
    """

    def __init__(self, cache_dir: str = "data/order_cache") -> None:
        """Initialize the order cache.

        Args:
            cache_dir: Directory path for cached order files.
        """
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

        self.current_order_id: Optional[int] = None
        self.current_details: Optional[List[Dict[str, Any]]] = None
        self.explanation: Optional[str] = None
        self.current_role: Optional[str] = None

    def _get_cache_path(self, order_id: int, role: str) -> str:
        """Build the file path for a cached order.

        Args:
            order_id: The order ID.
            role: The user role.

        Returns:
            Absolute path to the cache file.
        """
        return os.path.join(self.cache_dir, f"order_{order_id}_{role}.json")

    def save(
        self,
        order_id: int,
        order_details: List[Dict[str, Any]],
        explanation: str,
        role: str,
    ) -> bool:
        """Save order details to cache file.

        Args:
            order_id: The order ID to cache.
            order_details: Order detail data.
            explanation: Why this order was selected.
            role: User role for this cached version.

        Returns:
            True if save succeeded, False otherwise.
        """
        try:
            cache_data = {
                "order_details": order_details,
                "explanation": explanation,
                "role": role,
            }
            cache_path = self._get_cache_path(order_id, role)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error("Error saving to cache: %s", e)
            return False

    def load(
        self, order_id: int, role: str
    ) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        """Load order details from cache file.

        Args:
            order_id: The order ID to look up.
            role: The user role to match.

        Returns:
            Tuple of (order_details, explanation) or (None, None) if not cached.
        """
        try:
            cache_path = self._get_cache_path(order_id, role)
            if os.path.exists(cache_path):
                with open(cache_path, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                if cache_data.get("role") == role:
                    return cache_data["order_details"], cache_data["explanation"]
            return None, None
        except Exception as e:
            logger.error("Error loading from cache: %s", e)
            return None, None

    def set_current_order(
        self,
        order_id: int,
        order_details: List[Dict[str, Any]],
        explanation: str,
        role: str,
    ) -> None:
        """Set the currently active order and persist to cache.

        Args:
            order_id: The order ID.
            order_details: Order detail data.
            explanation: Why this order was selected.
            role: User role.
        """
        self.current_order_id = order_id
        self.current_details = order_details
        self.explanation = explanation
        self.current_role = role
        self.save(order_id, order_details, explanation, role)

    def clear(self) -> None:
        """Remove all cached order files."""
        try:
            for filename in os.listdir(self.cache_dir):
                filepath = os.path.join(self.cache_dir, filename)
                if os.path.isfile(filepath):
                    os.remove(filepath)
            logger.info("Order cache cleared")
        except Exception as e:
            logger.error("Error clearing cache: %s", e)
