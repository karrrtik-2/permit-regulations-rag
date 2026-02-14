"""
User authentication and information service for HeavyHaul AI.

Handles role verification, email validation, and user data retrieval
from MongoDB for drivers, clients, and admins.
"""

import logging
from typing import Any, Dict, Optional

from db import get_db

logger = logging.getLogger(__name__)

VALID_ROLES = ("admin", "client", "driver")


def verify_email(role: str, email: str) -> bool:
    """Verify that an email exists for a given role.

    Args:
        role: User role ('driver', 'client', or 'admin').
        email: Email address to verify.

    Returns:
        True if the email is valid for the role.
    """
    if role == "admin":
        return True

    try:
        db = get_db()
        collection = db.drivers if role == "driver" else db.clients
        return collection.find_one({"email": email}) is not None
    except Exception as e:
        logger.error("Error verifying email for %s: %s", role, e)
        return False


def get_user_info(role: str, email: str) -> Dict[str, Any]:
    """Retrieve user profile and order information.

    Args:
        role: User role ('driver', 'client', or 'admin').
        email: User's email address.

    Returns:
        Dictionary with role-specific user information, or error dict.
    """
    try:
        db = get_db()

        if role == "driver":
            user_data = db.drivers.find_one({"email": email})
            if not user_data:
                return {"error": "Driver not found"}
            return {
                "driver_info": {
                    "Full Name": (
                        f"{user_data.get('first_name', 'Unknown')} "
                        f"{user_data.get('surname', '')}"
                    ).strip(),
                    "Email": user_data.get("email", "Unknown"),
                    "Phone": user_data.get("phone", "Not Provided"),
                    "order_ids": user_data.get("order_ids", []),
                    "Open_Close Orders": user_data.get("order_status", {}),
                }
            }

        elif role == "client":
            user_data = db.clients.find_one({"email": email})
            if not user_data:
                return {"error": "Client not found"}
            return {
                "client_info": {
                    "Name": user_data.get("name", "Unknown"),
                    "Email": user_data.get("email", "Unknown"),
                    "Phone": user_data.get("phone", "Not Provided"),
                    "order_ids": user_data.get("order_ids", []),
                    "Open_Close Orders": user_data.get("order_status", {}),
                }
            }

        else:  # admin
            return {
                "admin_info": {
                    "role": "admin",
                    "access": "full",
                }
            }

    except Exception as e:
        logger.error("Error getting user info: %s", e)
        return {"error": "Error accessing the database"}


def get_order_ids_for_user(user_data: Dict[str, Any]) -> list:
    """Extract sorted order IDs from user data.

    Args:
        user_data: User info dictionary from get_user_info().

    Returns:
        List of order IDs sorted descending (newest first).
    """
    if "driver_info" in user_data:
        return sorted(user_data["driver_info"]["order_ids"], reverse=True)
    elif "client_info" in user_data:
        return sorted(user_data["client_info"]["order_ids"], reverse=True)
    return []
