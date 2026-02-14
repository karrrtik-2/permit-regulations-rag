"""
Shared test fixtures for HeavyHaul AI test suite.
"""

import os
import pytest

# Ensure test environment variables are set before importing settings
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/test_heavyhaul")
os.environ.setdefault("GROQ_API_KEY", "test_key_not_real")
os.environ.setdefault("OPENAI_API_KEY", "test_key_not_real")
os.environ.setdefault("WEATHER_API_KEY", "test_key_not_real")


@pytest.fixture
def sample_order():
    """Minimal order document for unit tests."""
    return {
        "order": {
            "id": 9999,
            "token": "abc123",
            "user_id": 1,
            "carrier_id": 2,
            "client_id": 3,
            "driver_id": 4,
            "order_status": "Open",
            "estimatedTotalCostValue": 5000,
            "order_created_date": "2024-06-15 10:30:00",
            "pickupFormattedAddress": "123 Main St, Dallas, TX",
            "deliveryFormatedAddress": "456 Oak Ave, Phoenix, AZ",
            "Trailer_Type": "Flatbed",
            "permitcount": 2,
            "routeData": [
                {
                    "id": 100,
                    "product_name": "Texas",
                    "start_date": "2024-06-16",
                    "permit_status": "Approved",
                    "price": 150.00,
                    "state_fee": 50.00,
                    "service_fee": 25.00,
                    "permit_link": None,
                    "route_image": None,
                    "metas": [],
                    "routeitem": [],
                    "meta_data": {},
                },
                {
                    "id": 101,
                    "product_name": "Arizona",
                    "start_date": "2024-06-17",
                    "permit_status": "Pending",
                    "price": 200.00,
                    "state_fee": 75.00,
                    "service_fee": 30.00,
                    "permit_link": None,
                    "route_image": None,
                    "metas": [],
                    "routeitem": [],
                    "meta_data": {},
                },
            ],
            "driverData": {
                "name": "John",
                "last_name": "Doe",
                "email": "john@example.com",
                "phone": "555-0100",
                "driver_meta_Data": {},
            },
            "clientData": {
                "name": "Jane",
                "last_name": "Smith",
                "email": "jane@example.com",
                "phone": "555-0200",
                "client_meta_Data": {},
            },
            "Company_Info": {
                "name": "Test Trucking Inc",
                "mc": "MC-12345",
                "dot": "DOT-67890",
                "Company_meta_data": {},
            },
            "truck_detail": {
                "make": "Peterbilt",
                "model": "389",
                "year": "2022",
                "truck_meta_data": {},
            },
            "Trailer_Info": {
                "type": "Flatbed",
                "length": "53ft",
                "trailer_meta_data": {},
            },
            "meta": {"tax": 100, "total": 5100, "subtotal": 5000},
            "Company_attribute_Info": [],
            "state_webstie_detail": [],
            "transactions": [],
            "odOrderLogData": [],
            "axle_spacing": [
                {"name": "Front", "value": "10ft"},
                {"name": "Rear", "value": "4ft"},
            ],
            "axle_weight": [
                {"name": "Front", "value": "12000"},
                {"name": "Rear", "value": "34000"},
            ],
        },
        "status": "Open",
        "id": 9999,
    }


@pytest.fixture
def sample_user():
    """Minimal user document for unit tests."""
    return {
        "name": "John",
        "last_name": "Doe",
        "email": "john@example.com",
        "role": "driver",
        "order_ids": [9999, 9998, 9997],
    }
