"""Unit tests for query processor filters."""

from pipelines.query_processor import (
    filter_by_order_status,
    filter_by_state,
    restructure_results,
    append_status_counts,
)


class TestFilterByOrderStatus:
    """Tests for order status filtering."""

    def test_filter_open(self):
        data = [
            {"order_id": 1, "order_status": "Open"},
            {"order_id": 2, "order_status": "Closed"},
            {"order_id": 3, "order_status": "Open"},
        ]
        result = filter_by_order_status(data, "show me open orders")
        assert len(result) == 2
        assert all(r["order_status"] == "Open" for r in result)

    def test_filter_closed(self):
        data = [
            {"order_id": 1, "order_status": "Open"},
            {"order_id": 2, "order_status": "Closed"},
        ]
        result = filter_by_order_status(data, "list closed orders")
        assert len(result) == 1
        assert result[0]["order_status"] == "Closed"

    def test_no_status_keyword_returns_all(self):
        data = [
            {"order_id": 1, "order_status": "Open"},
            {"order_id": 2, "order_status": "Closed"},
        ]
        result = filter_by_order_status(data, "show all orders")
        assert len(result) == 2


class TestFilterByState:
    """Tests for state-based route filtering."""

    def test_filters_to_matching_state(self):
        data = [
            {
                "order_id": 1,
                "routeData": [
                    {"state_name": "Texas - 2024-06-16"},
                    {"state_name": "Arizona - 2024-06-17"},
                ],
            }
        ]
        result = filter_by_state(data, "show texas orders")
        assert len(result) == 1
        assert len(result[0]["routeData"]) == 1
        assert "Texas" in result[0]["routeData"][0]["state_name"]

    def test_no_state_mentioned_returns_all(self):
        data = [{"order_id": 1, "routeData": [{"state_name": "Texas - 2024-06-16"}]}]
        result = filter_by_state(data, "show all orders")
        assert len(result) == 1


class TestAppendStatusCounts:
    """Tests for status count prepending."""

    def test_adds_counts(self):
        data = [
            {"order_id": 1, "order_status": "Open"},
            {"order_id": 2, "order_status": "Open"},
            {"order_id": 3, "order_status": "Closed"},
        ]
        result = append_status_counts(data)
        assert result[0]["total_open_orders"] == 2
        assert result[0]["total_closed_orders"] == 1

    def test_no_status_field(self):
        data = [{"order_id": 1}]
        result = append_status_counts(data)
        assert len(result) == 1
        assert "total_open_orders" not in result[0]


class TestRestructureResults:
    """Tests for result restructuring."""

    def test_groups_route_keys(self):
        data = [
            {
                "order_id": 1,
                "state_name": ["Texas - 2024-06-16", "Arizona - 2024-06-17"],
                "permit_status": ["Approved", "Pending"],
            }
        ]
        result = restructure_results(data)
        assert "routeData" in result[0]
        assert len(result[0]["routeData"]) == 2
        assert result[0]["routeData"][0]["state_name"] == "Texas - 2024-06-16"
