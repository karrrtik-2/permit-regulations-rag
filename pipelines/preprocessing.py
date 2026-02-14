"""
Order data preprocessing pipeline for HeavyHaul AI.

Transforms raw API order data into a clean, structured format
suitable for MongoDB storage and downstream consumption.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def preprocess_order_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Transform raw order data into standardized format.

    Performs field renaming, data separation (admin vs. public),
    and route data restructuring for consistent storage.

    Args:
        data: Raw order data from the API.

    Returns:
        Preprocessed order data dictionary.
    """
    order = data["order"]

    # Rename status fields
    if "status" in order:
        order["order_status"] = order.pop("status")
    if "estimatorTotalPriceValue" in order:
        order["estimatedTotalCostValue"] = order.pop("estimatorTotalPriceValue")
    if "getRoutesData" in order:
        order["onlyForRouteIdeas"] = order.pop("getRoutesData")

    # Rename route statuses
    for route in order.get("routeData", []):
        if "status" in route:
            route["permit_status"] = route.pop("status")

    # Extract admin-only metadata
    admin_data = _extract_admin_metadata(order)

    # Reorder fields with priority keys first
    new_order = _build_ordered_dict(order, admin_data)

    # Process sub-entities
    _process_truck_detail(new_order)
    _process_trailer_detail(new_order)
    _process_company_info(new_order)
    _process_company_attributes(new_order)
    _process_client_data(new_order)
    _process_driver_data(new_order)
    _process_route_data(new_order)

    data["order"] = new_order
    return data


def _extract_admin_metadata(order: Dict[str, Any]) -> Dict[str, Any]:
    """Extract admin-only fields from order into separate metadata dict."""
    return {
        "tax": order.pop("tax", 0),
        "total": order.pop("total", 0),
        "subtotal": order.pop("subtotal", 0),
        "created_at": order.pop("created_at", None),
        "updated_at": order.pop("updated_at", None),
        "tollPassDeviceAttributes": order.pop("tollPassDeviceAttributes", None),
        "EmptyWeightAttributes": order.pop("EmptyWeightAttributes", None),
    }


def _build_ordered_dict(
    order: Dict[str, Any], admin_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Build a new order dict with priority field ordering."""
    priority_keys = (
        "id", "token", "user_id", "carrier_id",
        "client_id", "driver_id", "order_status",
        "estimatedTotalCostValue",
    )

    new_order: Dict[str, Any] = {}
    for key in priority_keys:
        if key in order:
            new_order[key] = order.get(key)

    # Add remaining fields
    for key, value in order.items():
        if key not in new_order:
            new_order[key] = value

    new_order["meta"] = admin_data
    return new_order


def _extract_fields(
    source: Dict[str, Any], field_names: List[str]
) -> Dict[str, Any]:
    """Pop multiple fields from a dict into a new metadata dict."""
    return {field: source.pop(field, None) for field in field_names}


def _process_truck_detail(order: Dict[str, Any]) -> None:
    """Separate truck admin metadata from public detail."""
    truck = order.get("truck_detail", {})
    if not truck:
        return

    meta_fields = [
        "token", "owner_id", "owner_pay", "registration",
        "lease_agreement", "insurance", "annual_inspection",
        "registration_exp", "insurance_exp", "annual_inspection_exp",
        "status", "is_brk_updates_enabled", "ny_permit", "ny_permit_exp",
        "nm_permit", "nm_permit_exp", "carb_certificate", "oregon_permit",
        "eld_device", "tst_sn", "loss_payee_name", "loss_payee_address",
        "unit_value", "created_at", "updated_at",
    ]
    truck["truck_meta_data"] = _extract_fields(truck, meta_fields)


def _process_trailer_detail(order: Dict[str, Any]) -> None:
    """Separate trailer admin metadata from public detail."""
    trailer = order.get("Trailer_Info", {})
    if not trailer:
        return

    meta_fields = [
        "token", "owner_id", "registration", "lease_agreement",
        "insurance", "annual_inspection", "name_on_registration",
        "status", "unit_value", "loss_payee_name", "loss_payee_address",
        "registration_exp", "insurance_exp", "annual_inspection_exp",
        "created_at", "updated_at",
    ]
    trailer["trailer_meta_data"] = _extract_fields(trailer, meta_fields)


def _process_company_info(order: Dict[str, Any]) -> None:
    """Separate company admin metadata from public info."""
    company = order.get("Company_Info", {})
    if not company:
        return

    meta_fields = [
        "token", "tax_id", "billing_company_name", "billing_email",
        "billing_address", "billing_city", "billing_state",
        "billing_zip_code", "created_at", "updated_at", "carrier_credits",
    ]
    company["Company_meta_data"] = _extract_fields(company, meta_fields)


def _process_company_attributes(order: Dict[str, Any]) -> None:
    """Move company attribute fields into the attributes list."""
    attrs = order.get("Company_attribute_Info", [])

    for field_name in ("Company_expire_date", "Company_carrierImage"):
        if field_name in order:
            attrs.append({"name": field_name, "value": order.pop(field_name)})


def _process_client_data(order: Dict[str, Any]) -> None:
    """Separate client admin metadata from public data."""
    client = order.get("clientData", {})
    if not client:
        return

    meta_fields = [
        "token", "otp", "photo", "birthday", "cdl",
        "email_verified_at", "is_assistant", "status", "hire_date",
        "pay_rate", "created_at", "updated_at", "tier",
        "billing_email", "billing_company_name", "billing_tax_id",
        "billing_address", "billing_city", "billing_state",
        "billing_zip", "default_carrier_id", "credits",
    ]
    client["client_meta_Data"] = _extract_fields(client, meta_fields)


def _process_driver_data(order: Dict[str, Any]) -> None:
    """Separate driver admin metadata from public data."""
    driver = order.get("driverData", {})
    if not driver:
        return

    meta_fields = [
        "is_assistant", "status", "hire_date", "pay_rate",
        "created_at", "updated_at", "tier",
    ]
    driver["driver_meta_Data"] = _extract_fields(driver, meta_fields)


def _process_route_data(order: Dict[str, Any]) -> None:
    """Process route data: extract links, URLs, and separate metadata."""
    for route in order.get("routeData", []):
        route["permit_link"] = None
        route["route_image"] = None

        # Extract links from metas
        for meta in route.get("metas", []):
            for value in meta.get("value", []):
                if isinstance(value, str):
                    lower_val = value.lower()
                    if lower_val.endswith(".pdf"):
                        route["permit_link"] = value
                    elif lower_val.endswith((".jpg", ".jpeg", ".png", ".gif")):
                        route["route_image"] = value

        # Extract route URLs from routeitem
        for i, item in enumerate(route.get("routeitem", []), start=1):
            route[f"route_url_{i}"] = item.get("route_url")
            route[f"route_url_status_{i}"] = item.get("status")

        # Remove raw fields
        route.pop("metas", None)
        route.pop("routeitem", None)

        # Build metadata based on status
        if route.get("permit_status") == "Delete":
            meta_fields = [
                "price", "use_tolls", "state_fee", "other_fee", "token",
                "service_fee", "attached_at", "state_id", "permit_link",
                "route_image", "quantity", "created_at", "updated_at",
            ]
        else:
            meta_fields = ["quantity", "created_at", "updated_at", "token"]

        route["meta_data"] = _extract_fields(route, meta_fields)
