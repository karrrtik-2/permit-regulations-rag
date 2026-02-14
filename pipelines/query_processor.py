"""
Query processing pipeline for MongoDB order data.

Uses LLM to extract relevant keys from user queries and
fetches corresponding data from MongoDB with filtering
by state, date, and order status.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from config.constants import (
    LAST_N_MONTHS_KEYWORDS,
    MONTHS,
    PAST_30_DAYS_KEYWORDS,
    ROUTE_DATA_KEYS,
    STATES_LOWER,
)
from config.settings import settings
from db import get_db
from services.llm_client import get_llm

logger = logging.getLogger(__name__)

# Prompt for key extraction
KEY_EXTRACTION_PROMPT = """You are a very intelligent AI assistant who is expert in identifying exact relevant keys from order schema according to the user's query.
Important Note: You just have to return the relevant keys to the user's query from the sample order schema nothing else.
Return only comma-separated key names."""


# ─── Data Fetchers ────────────────────────────────────────────────────────────

def _fetch_nested(data: Dict, *keys: str, default: str = "Key not found") -> Any:
    """Safely traverse nested dictionary keys."""
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, default)
        else:
            return default
    return current


def fetch_order_id(data: Dict) -> Any:
    return _fetch_nested(data, "order", "id")


def fetch_order_status(data: Dict) -> Any:
    return _fetch_nested(data, "order", "order_status")


def fetch_order_created_date(data: Dict) -> Any:
    return _fetch_nested(data, "order", "order_created_date")


def fetch_state_names(data: Dict) -> List[str]:
    route_data = _fetch_nested(data, "order", "routeData", default=[])
    if not isinstance(route_data, list):
        return []
    return [
        f"{item.get('product_name', 'Unknown')} - {item.get('start_date', 'Unknown')}"
        for item in route_data
    ]


def fetch_route_field(data: Dict, field: str) -> List[Any]:
    route_data = _fetch_nested(data, "order", "routeData", default=[])
    if not isinstance(route_data, list):
        return []
    return [item.get(field, "Key not found") for item in route_data]


def fetch_axle_data(data: Dict, field: str) -> Any:
    items = _fetch_nested(data, "order", field, default=[])
    if not isinstance(items, list):
        return "Key not found"
    result = {item["name"]: item["value"] for item in items if "name" in item}
    return result if result else "Key not found"


# Key-to-function mapping
KEY_FUNCTIONS: Dict[str, Any] = {
    "order_id": fetch_order_id,
    "order_status": fetch_order_status,
    "order_created_date": fetch_order_created_date,
    "axle_spacing": lambda d: fetch_axle_data(d, "axle_spacing"),
    "axle_weight": lambda d: fetch_axle_data(d, "axle_weight"),
    "estimatedTotalCostValue": lambda d: _fetch_nested(d, "order", "estimatedTotalCostValue"),
    "Trailer_Type": lambda d: _fetch_nested(d, "order", "Trailer_Type"),
    "pickup_Address": lambda d: _fetch_nested(d, "order", "pickupFormattedAddress"),
    "delivery_Address": lambda d: _fetch_nested(d, "order", "deliveryFormatedAddress"),
    "permitcount": lambda d: _fetch_nested(d, "order", "permitcount"),
    "$totalPaidAmount": lambda d: _fetch_nested(d, "order", "$totalPaidAmount"),
    "total_due": lambda d: _fetch_nested(d, "order", "total_due"),
    "state_name": fetch_state_names,
    "permit_status": lambda d: fetch_route_field(d, "permit_status"),
    "permit_info": lambda d: fetch_route_field(d, "permit_info"),
    "state_fee": lambda d: fetch_route_field(d, "state_fee"),
    "price": lambda d: fetch_route_field(d, "price"),
    "client_name": lambda d: _fetch_nested(d, "order", "clientData", "name"),
    "client_phone": lambda d: _fetch_nested(d, "order", "clientData", "phone"),
    "driver_name": lambda d: _fetch_nested(d, "order", "driverData", "name"),
    "driver_phone": lambda d: _fetch_nested(d, "order", "driverData", "phone"),
}


# ─── Filters ─────────────────────────────────────────────────────────────────

def filter_by_state(results: List[Dict], query: str) -> List[Dict]:
    """Filter results to only include routes matching mentioned states."""
    query_lower = query.lower()
    targets = [s for s in STATES_LOWER if s in query_lower]

    if not targets:
        return results

    filtered = []
    for result in results:
        if "routeData" not in result:
            filtered.append(result)
            continue

        matching_routes = [
            rd for rd in result["routeData"]
            if rd.get("state_name", "").split(" - ")[0].lower() in targets
        ]
        if matching_routes:
            new_result = {**result, "routeData": matching_routes}
            filtered.append(new_result)

    return filtered


def filter_by_order_status(results: List[Dict], query: str) -> List[Dict]:
    """Filter results by open/closed order status keywords."""
    q = query.lower()
    want_open = "open" in q
    want_closed = any(w in q for w in ("closed", "completed", "complete"))

    if not want_open and not want_closed:
        return results

    return [
        r for r in results
        if "order_status" in r and (
            (want_open and r["order_status"].lower() == "open")
            or (want_closed and r["order_status"].lower() in ("closed", "completed"))
        )
    ]


def filter_by_date(results: List[Dict], query: str) -> List[Dict]:
    """Filter results by date-related keywords in the query."""
    q = query.lower()
    today = datetime.today()
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    if any(kw in q for kw in PAST_30_DAYS_KEYWORDS):
        start_date = today - timedelta(days=30)
        end_date = today
    elif "last month" in q:
        first = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        last = today.replace(day=1) - timedelta(days=1)
        start_date, end_date = first, last
    elif "last two months" in q or "past two months" in q:
        first = (today.replace(day=1) - timedelta(days=1)).replace(day=1) - timedelta(days=30)
        last = today.replace(day=1) - timedelta(days=1)
        start_date, end_date = first, last
    else:
        # Check "last N months"
        n_months_key = next(
            (k for k in LAST_N_MONTHS_KEYWORDS if f"last {k} months" in q or f"past {k} months" in q),
            None,
        )
        if n_months_key:
            n = LAST_N_MONTHS_KEYWORDS[n_months_key]
            start_date = (today.replace(day=1) - timedelta(days=1)).replace(day=1) - timedelta(days=30 * (n - 1))
            end_date = today.replace(day=1) - timedelta(days=1)
        else:
            # Check specific month name
            target_month = next((m for m in MONTHS if m in q), None)
            if target_month:
                month_idx = MONTHS.index(target_month) + 1
                year = today.year if month_idx <= today.month else today.year - 1
                start_date = datetime(year, month_idx, 1)
                if month_idx < 12:
                    end_date = datetime(year, month_idx + 1, 1) - timedelta(days=1)
                else:
                    end_date = datetime(year + 1, 1, 1) - timedelta(days=1)

    if start_date is None or end_date is None:
        return results

    filtered = []
    for r in results:
        date_str = r.get("order_created_date")
        if not date_str:
            continue
        try:
            order_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            if start_date <= order_date <= end_date:
                filtered.append(r)
        except ValueError:
            logger.warning("Invalid date format: %s", date_str)

    return filtered


def filter_by_last_order(data_list: List[Dict], query: str) -> List[Dict]:
    """Filter to specific order position (latest, second last, etc.)."""
    q = query.lower()
    position_map = {
        "latest order": -1, "last order": -1,
        "second latest order": -2, "second last order": -2,
        "third latest order": -3, "third last order": -3,
    }

    for text, idx in sorted(position_map.items(), key=lambda x: len(x[0]), reverse=True):
        if text in q and data_list and len(data_list) >= abs(idx):
            return [data_list[idx]]

    return data_list


def restructure_results(results: List[Dict]) -> List[Dict]:
    """Reorganize flat route-level keys into nested routeData structure."""
    restructured = []

    for result in results:
        new_result = {"order_id": result["order_id"]}
        route_data = []
        route_keys = ROUTE_DATA_KEYS

        if any(k in result for k in route_keys):
            list_len = len(next((result[k] for k in route_keys if k in result), []))

            for i in range(list_len):
                state_data = {}
                if "state_name" in result and i < len(result["state_name"]):
                    state_data["state_name"] = result["state_name"][i]
                for key in route_keys:
                    if key != "state_name" and key in result and i < len(result[key]):
                        state_data[key] = result[key][i]
                route_data.append(state_data)

            if route_data:
                new_result["routeData"] = route_data

        for key, value in result.items():
            if key not in route_keys and key != "order_id":
                new_result[key] = value

        restructured.append(new_result)

    return restructured


def append_status_counts(results: List[Dict]) -> List[Dict]:
    """Prepend open/closed order counts to results list."""
    if not results or "order_status" not in results[0]:
        return results

    open_count = sum(1 for r in results if r.get("order_status", "").lower() == "open")
    closed_count = sum(
        1 for r in results
        if r.get("order_status", "").lower() in ("closed", "completed")
    )

    counts = {}
    if open_count:
        counts["total_open_orders"] = open_count
    if closed_count:
        counts["total_closed_orders"] = closed_count

    if counts:
        results.insert(0, counts)

    return results


# ─── Main Query Processing ───────────────────────────────────────────────────

def get_user_orders(email: str) -> Optional[List[Dict]]:
    """Fetch all orders for a user by email.

    Args:
        email: User's email address.

    Returns:
        List of order documents, or None.
    """
    db = get_db()
    user = db.clients.find_one({"email": email})

    if not user:
        logger.warning("No user found with email: %s", email)
        return None

    order_ids = user.get("order_ids", [])
    if not order_ids:
        return None

    orders = list(db.orders.find({"id": {"$in": order_ids}}))
    return orders if orders else None


def ask_llm_for_keys(question: str) -> str:
    """Ask the LLM to identify relevant order schema keys.

    Args:
        question: The user's natural language query.

    Returns:
        Comma-separated string of relevant keys.
    """
    llm = get_llm()
    messages = [
        {"role": "system", "content": KEY_EXTRACTION_PROMPT},
        {"role": "user", "content": question},
    ]
    return llm.chat(
        messages,
        model=settings.llm.groq_fast_model,
        temperature=0.1,
        max_tokens=80,
    )


def process_query(
    query: str, data_list: List[Dict]
) -> str:
    """Process a user query against order data.

    Asks LLM for relevant keys, fetches data, applies filters,
    and returns formatted results.

    Args:
        query: The user's natural language query.
        data_list: List of order documents from MongoDB.

    Returns:
        Formatted JSON string of results.
    """
    llm_response = ask_llm_for_keys(query)

    # Parse keys from LLM response
    keys = []
    for key in llm_response.split(","):
        key = key.strip().strip('"')
        keys.append(key.split(".")[-1] if "." in key else key)

    q_lower = query.lower()

    # Auto-add state_name if route data keys are present
    if (
        any(k in ROUTE_DATA_KEYS for k in keys)
        or any(s in q_lower for s in STATES_LOWER)
    ) and "state_name" not in keys:
        keys.append("state_name")

    # Auto-add date if time-related keywords present
    date_keywords = ("month", "months", "year", "week", "weeks")
    if any(kw in q_lower for kw in date_keywords) and "order_created_date" not in keys:
        keys.append("order_created_date")

    # Filter by position first
    filtered_data = filter_by_last_order(data_list, query)

    # Fetch data for each key
    results = []
    for data in filtered_data:
        result = {"order_id": fetch_order_id(data)}
        for key in keys:
            if key in KEY_FUNCTIONS:
                result[key] = KEY_FUNCTIONS[key](data)
        results.append(result)

    # Apply all filters
    results = restructure_results(results)
    results = filter_by_order_status(results, query)
    results = filter_by_date(results, query)
    results = filter_by_state(results, query)
    results = append_status_counts(results)

    return json.dumps(results, indent=2)
