"""Unit tests for role-based data filtering."""

import copy
from services.data_filter import (
    filter_order_by_role,
    filter_order_for_admin,
    filter_order_for_client,
    filter_order_for_driver,
)


class TestFilterOrderForDriver:
    """Tests for driver role filtering."""

    def test_removes_meta_fields(self, sample_order):
        order = copy.deepcopy(sample_order["order"])
        filtered = filter_order_for_driver(order)

        assert "meta" not in filtered
        assert "transactions" not in filtered
        assert "Company_attribute_Info" not in filtered

    def test_removes_nested_meta(self, sample_order):
        order = copy.deepcopy(sample_order["order"])
        filtered = filter_order_for_driver(order)

        if "truck_detail" in filtered:
            assert "truck_meta_data" not in filtered["truck_detail"]
        if "driverData" in filtered:
            assert "driver_meta_Data" not in filtered["driverData"]

    def test_preserves_core_fields(self, sample_order):
        order = copy.deepcopy(sample_order["order"])
        filtered = filter_order_for_driver(order)

        assert "id" in filtered
        assert "order_status" in filtered


class TestFilterOrderForClient:
    """Tests for client role filtering."""

    def test_removes_meta_fields(self, sample_order):
        order = copy.deepcopy(sample_order["order"])
        filtered = filter_order_for_client(order)

        assert "meta" not in filtered
        assert "transactions" not in filtered

    def test_preserves_route_data(self, sample_order):
        order = copy.deepcopy(sample_order["order"])
        filtered = filter_order_for_client(order)

        assert "routeData" in filtered
        assert len(filtered["routeData"]) == 2


class TestFilterOrderForAdmin:
    """Tests for admin role filtering."""

    def test_keeps_meta(self, sample_order):
        order = copy.deepcopy(sample_order["order"])
        filtered = filter_order_for_admin(order)

        # Admin should still have meta (not in admin exclusion list for meta_data etc)
        assert "id" in filtered
        assert "order_status" in filtered

    def test_removes_only_admin_exclusions(self, sample_order):
        order = copy.deepcopy(sample_order["order"])
        filtered = filter_order_for_admin(order)

        assert "odOrderLogData" not in filtered
        assert "Company_attribute_Info" not in filtered


class TestFilterOrderByRole:
    """Tests for the role dispatcher function."""

    def test_driver_role(self, sample_order):
        order = copy.deepcopy(sample_order["order"])
        filtered = filter_order_by_role(order, "driver")
        assert "meta" not in filtered

    def test_client_role(self, sample_order):
        order = copy.deepcopy(sample_order["order"])
        filtered = filter_order_by_role(order, "client")
        assert "meta" not in filtered

    def test_admin_role(self, sample_order):
        order = copy.deepcopy(sample_order["order"])
        filtered = filter_order_by_role(order, "admin")
        assert "id" in filtered

    def test_unknown_role_returns_original(self, sample_order):
        """Unknown roles should return unmodified data."""
        order = copy.deepcopy(sample_order["order"])
        filtered = filter_order_by_role(order, "unknown")
        assert "id" in filtered
