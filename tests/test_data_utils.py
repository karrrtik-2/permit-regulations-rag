"""Unit tests for data utility functions."""

from utils.data import remove_deleted_permits, remove_null_fields


class TestRemoveNullFields:
    """Tests for remove_null_fields()."""

    def test_removes_none_values(self):
        data = {"a": 1, "b": None, "c": "hello"}
        result = remove_null_fields(data)
        assert result == {"a": 1, "c": "hello"}

    def test_removes_empty_strings(self):
        data = {"a": "value", "b": ""}
        result = remove_null_fields(data)
        assert result == {"a": "value"}

    def test_recursive_removal(self):
        data = {"a": {"b": None, "c": 1}, "d": 2}
        result = remove_null_fields(data)
        assert result == {"a": {"c": 1}, "d": 2}

    def test_handles_lists(self):
        data = {"items": [{"a": None, "b": 1}, {"c": ""}]}
        result = remove_null_fields(data)
        assert result["items"][0] == {"b": 1}

    def test_empty_dict(self):
        assert remove_null_fields({}) == {}

    def test_preserves_zero_and_false(self):
        data = {"zero": 0, "false": False, "none": None}
        result = remove_null_fields(data)
        assert result == {"zero": 0, "false": False}


class TestRemoveDeletedPermits:
    """Tests for remove_deleted_permits()."""

    def test_removes_deleted_routes(self):
        order = {
            "routeData": [
                {"product_name": "Texas", "permit_status": "Approved"},
                {"product_name": "Arizona", "permit_status": "Delete"},
                {"product_name": "California", "permit_status": "Pending"},
            ]
        }
        result = remove_deleted_permits(order)
        assert len(result["routeData"]) == 2
        names = [r["product_name"] for r in result["routeData"]]
        assert "Arizona" not in names

    def test_no_route_data(self):
        order = {"id": 123}
        result = remove_deleted_permits(order)
        assert result == {"id": 123}

    def test_all_deleted(self):
        order = {
            "routeData": [
                {"permit_status": "Delete"},
                {"permit_status": "Delete"},
            ]
        }
        result = remove_deleted_permits(order)
        assert result["routeData"] == []

    def test_none_deleted(self):
        order = {
            "routeData": [
                {"permit_status": "Approved"},
                {"permit_status": "Pending"},
            ]
        }
        result = remove_deleted_permits(order)
        assert len(result["routeData"]) == 2
