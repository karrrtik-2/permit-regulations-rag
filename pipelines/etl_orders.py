"""
ETL pipeline for ingesting orders into MongoDB.

Fetches order data from the external API, preprocesses it,
and upserts into MongoDB collections (orders, drivers, clients, companies).
"""

import logging
import os
import re
from typing import Any, Dict, List, Optional

import pdfplumber
import requests

from config.settings import settings
from db import get_db
from pipelines.preprocessing import preprocess_order_data

logger = logging.getLogger(__name__)


def extract_order_data(order: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and flatten order details for MongoDB storage.

    Args:
        order: Raw order data from API.

    Returns:
        Flattened order document.
    """
    order_details = order.get("order", {})
    return {
        "id": order_details.get("id"),
        **order_details,
        "status": order_details.get("order_status"),
    }


def insert_order(order_data: Dict[str, Any]) -> Dict[str, Any]:
    """Upsert an order document into MongoDB.

    Args:
        order_data: Processed order data.

    Returns:
        The inserted/updated order data.
    """
    db = get_db()
    db.orders.update_one(
        {"id": order_data["id"]},
        {"$set": order_data},
        upsert=True,
    )
    return order_data


def update_driver(order: Dict[str, Any]) -> None:
    """Update driver collection with order association.

    Args:
        order: Order data containing driver information.
    """
    driver_data = order.get("order", {}).get("driverData", {})
    if not driver_data or not driver_data.get("email"):
        logger.debug("Driver data missing, skipping driver update.")
        return

    db = get_db()
    email = driver_data["email"]
    first_name = driver_data.get("name", "")
    surname = driver_data.get("last_name", "")

    # Initialize order_status if not exists
    db.drivers.update_one(
        {"email": email},
        {"$setOnInsert": {"order_status": {"open_orders": [], "closed_orders": []}}},
        upsert=True,
    )

    # Build update based on order status
    is_open = order.get("status") == "Open"
    add_to = "order_status.open_orders" if is_open else "order_status.closed_orders"
    pull_from = "order_status.closed_orders" if is_open else "order_status.open_orders"

    db.drivers.update_one(
        {"email": email},
        {
            "$set": {
                "first_name": first_name,
                "surname": surname,
                "full_name": f"{first_name} {surname}".strip(),
                "phone": driver_data.get("phone"),
            },
            "$addToSet": {"order_ids": order["id"], add_to: order["id"]},
            "$pull": {pull_from: order["id"]},
        },
    )

    # Sort arrays descending
    _sort_order_arrays(db.drivers, {"email": email})


def update_client(order: Dict[str, Any]) -> None:
    """Update client collection with order association.

    Args:
        order: Order data containing client information.
    """
    client_data = order.get("order", {}).get("clientData", {})
    if not client_data or not client_data.get("email"):
        logger.debug("Client data missing, skipping client update.")
        return

    db = get_db()
    email = client_data["email"]

    db.clients.update_one(
        {"email": email},
        {"$setOnInsert": {"order_status": {"open_orders": [], "closed_orders": []}}},
        upsert=True,
    )

    is_open = order.get("status") == "Open"
    add_to = "order_status.open_orders" if is_open else "order_status.closed_orders"
    pull_from = "order_status.closed_orders" if is_open else "order_status.open_orders"

    db.clients.update_one(
        {"email": email},
        {
            "$set": client_data,
            "$addToSet": {"order_ids": order["id"], add_to: order["id"]},
            "$pull": {pull_from: order["id"]},
        },
    )

    _sort_order_arrays(db.clients, {"email": email})


def update_company(order: Dict[str, Any]) -> None:
    """Update company collection with order association.

    Args:
        order: Order data containing company information.
    """
    order_inner = order.get("order", {})
    mc_number = order_inner.get("Company_Info", {}).get("mc")
    if not mc_number:
        logger.debug("No MC number, skipping company update.")
        return

    db = get_db()
    company_info = {
        "Company_Info": {
            "Company_Name": order_inner.get("Company_Info", {}).get("name"),
            "MC_Number": mc_number,
            "DOT_Number": order_inner.get("Company_Info", {}).get("dot"),
            "Tax_ID": order_inner.get("Company_Info", {}).get("tax_id"),
            "IFTA_License_Number": order_inner.get("Company_Info", {}).get("ifta_number"),
            "Email": order_inner.get("Company_email"),
            "Phone_Number": order_inner.get("Company_phone_number"),
            "Physical_Address": order_inner.get("Company_physical_address"),
            "City": order_inner.get("Company_city"),
            "State": order_inner.get("Company_state"),
            "ZIP_Code": order_inner.get("Company_zip_code"),
            "Liability_COI": order_inner.get("Company_expire_date"),
        }
    }

    db.companies.update_one(
        {"Company_Info.MC_Number": mc_number},
        {"$setOnInsert": {"order_status": {"open_orders": [], "closed_orders": []}}},
        upsert=True,
    )

    is_open = order.get("status") == "Open"
    add_to = "order_status.open_orders" if is_open else "order_status.closed_orders"
    pull_from = "order_status.closed_orders" if is_open else "order_status.open_orders"

    db.companies.update_one(
        {"Company_Info.MC_Number": mc_number},
        {
            "$set": company_info,
            "$addToSet": {"order_ids": order["id"], add_to: order["id"]},
            "$pull": {pull_from: order["id"]},
        },
    )

    _sort_order_arrays(db.companies, {"Company_Info.MC_Number": mc_number})


def _sort_order_arrays(collection: Any, filter_query: Dict[str, Any]) -> None:
    """Sort order_ids and status arrays in descending order.

    Args:
        collection: MongoDB collection.
        filter_query: Document filter.
    """
    collection.update_one(
        filter_query,
        [
            {
                "$set": {
                    "order_ids": {"$sortArray": {"input": "$order_ids", "sortBy": -1}},
                    "order_status.open_orders": {
                        "$sortArray": {"input": "$order_status.open_orders", "sortBy": -1}
                    },
                    "order_status.closed_orders": {
                        "$sortArray": {"input": "$order_status.closed_orders", "sortBy": -1}
                    },
                }
            }
        ],
    )


def extract_text_from_pdf(pdf_url: str) -> Optional[str]:
    """Download and extract text from a PDF URL.

    Args:
        pdf_url: URL of the PDF file.

    Returns:
        Extracted text, or None on failure.
    """
    temp_path = "temp_etl.pdf"
    try:
        response = requests.get(pdf_url, timeout=30)
        if response.status_code != 200:
            logger.error("Failed to download PDF: %s", pdf_url)
            return None

        with open(temp_path, "wb") as f:
            f.write(response.content)

        extracted_text = []
        with pdfplumber.open(temp_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    extracted_text.append(text)

        return " ".join(extracted_text) if extracted_text else None

    except Exception as e:
        logger.error("Error extracting text from PDF %s: %s", pdf_url, e)
        return None
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def process_route_permits(order_data: Dict[str, Any]) -> None:
    """Process permit PDFs from route data and store extracted text.

    Args:
        order_data: Order document with routeData.
    """
    db = get_db()
    route_data = order_data.get("order", {}).get("routeData", [])

    for route in route_data:
        state_id = route.get("id")
        state_name = route.get("product_name")

        for meta in route.get("metas", []):
            if meta.get("key") != "step2Image1":
                continue

            for url in meta.get("value", []):
                if not isinstance(url, str) or not url.lower().endswith(".pdf"):
                    continue

                logger.info("Processing permit PDF for %s: %s", state_name, url)
                text = extract_text_from_pdf(url)
                if text:
                    db.orders.update_one(
                        {"order.routeData.id": state_id},
                        {"$set": {"order.routeData.$.permit_info": {"extracted_text": text}}},
                    )


def process_api_order(order_id: str) -> None:
    """Fetch, preprocess, and ingest a single order from the API.

    Args:
        order_id: The order ID to process.
    """
    url = f"{settings.etl.api_base_url}{order_id}"
    logger.info("Fetching order %s from %s", order_id, url)

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        orders = data if isinstance(data, list) else [data]

        for order in orders:
            preprocessed = preprocess_order_data(order)
            order_data = extract_order_data(order)
            inserted = insert_order(order_data)

            update_driver(inserted)
            update_client(inserted)
            update_company(inserted)
            process_route_permits(order)

        logger.info("Successfully processed order %s", order_id)

    except requests.RequestException as e:
        logger.error("API request failed for order %s: %s", order_id, e)
    except Exception as e:
        logger.error("Error processing order %s: %s", order_id, e)
