import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import IntEnum
from typing import Any, Dict, List, Optional, Set

from db import get_db
from services.llm_client import get_llm
from services.location_weather import get_weather_by_city

logger = logging.getLogger(__name__)


# ─── Alert Priority ──────────────────────────────────────────────────────────


class AlertPriority(IntEnum):
    """Alert priority levels. Lower value = higher priority."""

    CRITICAL = 1  # Immediate attention (severe weather, order cancelled)
    HIGH = 2  # Important (order status change, permit expiring soon)
    MEDIUM = 3  # Noteworthy (new order assignment, delivery approaching)
    LOW = 4  # Informational (routine updates)


# ─── Alert Data Model ────────────────────────────────────────────────────────


@dataclass
class ProactiveAlert:
    """A single proactive alert to be delivered to the user."""

    alert_type: str  # e.g., "order_status", "permit_expiry", "weather", etc.
    priority: AlertPriority
    title: str  # Short title for logging
    message: str  # Full spoken message for TTS
    order_id: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    delivered: bool = False

    def __lt__(self, other: "ProactiveAlert") -> bool:
        """Compare by priority (lower value = higher priority)."""
        return self.priority < other.priority


# ─── Proactive Monitor ───────────────────────────────────────────────────────


class ProactiveMonitor:
    """Background monitor that detects changes and generates alerts.

    Periodically polls MongoDB for order updates, permit expirations,
    weather conditions, and deadline proximity. Generates prioritized
    alerts that are queued for the voice assistant to deliver.

    Attributes:
        user_role: The active user's role.
        user_email: The active user's email.
        poll_interval: Seconds between monitoring cycles.
        alert_queue: Priority-sorted queue of pending alerts.
    """

    def __init__(
        self,
        user_role: str,
        user_email: str,
        poll_interval: int = 120,
        weather_interval: int = 1800,
        permit_warning_days: int = 3,
        deadline_warning_hours: int = 24,
    ) -> None:
        """Initialize the proactive monitor.

        Args:
            user_role: Active user role ('admin', 'driver', 'client').
            user_email: Active user email.
            poll_interval: Seconds between order/permit checks.
            weather_interval: Seconds between weather checks.
            permit_warning_days: Days before permit expiry to warn.
            deadline_warning_hours: Hours before deadline to remind.
        """
        self.user_role = user_role
        self.user_email = user_email
        self.poll_interval = poll_interval
        self.weather_interval = weather_interval
        self.permit_warning_days = permit_warning_days
        self.deadline_warning_hours = deadline_warning_hours

        # Alert queue and deduplication
        self.alert_queue: List[ProactiveAlert] = []
        self._delivered_keys: Set[str] = set()

        # Snapshot of previous state for change detection
        self._last_order_statuses: Dict[int, str] = {}
        self._last_order_ids: Set[int] = set()
        self._warned_permits: Set[str] = set()
        self._warned_deadlines: Set[int] = set()

        # Control flags
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._weather_task: Optional[asyncio.Task] = None

    # ─── Lifecycle ────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start background monitoring tasks."""
        if self._running:
            logger.warning("Proactive monitor already running")
            return

        self._running = True
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._monitor_loop())
        self._weather_task = loop.create_task(self._weather_loop())
        logger.info(
            "Proactive monitor started (poll=%ds, weather=%ds)",
            self.poll_interval,
            self.weather_interval,
        )

    def stop(self) -> None:
        """Stop all background monitoring tasks."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        if self._weather_task and not self._weather_task.done():
            self._weather_task.cancel()
        logger.info("Proactive monitor stopped")

    @property
    def has_alerts(self) -> bool:
        """Check if there are pending undelivered alerts."""
        return any(not a.delivered for a in self.alert_queue)

    def get_pending_alerts(self) -> List[ProactiveAlert]:
        """Get all pending alerts sorted by priority.

        Returns:
            List of undelivered alerts, highest priority first.
        """
        pending = [a for a in self.alert_queue if not a.delivered]
        pending.sort()
        return pending

    def mark_delivered(self, alert: ProactiveAlert) -> None:
        """Mark an alert as delivered so it won't be repeated."""
        alert.delivered = True
        key = self._alert_key(alert)
        self._delivered_keys.add(key)

    def clear_old_alerts(self, max_age_hours: int = 24) -> None:
        """Remove delivered alerts older than max_age_hours."""
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        self.alert_queue = [
            a for a in self.alert_queue
            if not a.delivered or a.created_at > cutoff
        ]

    # ─── Background Loops ────────────────────────────────────────────────

    async def _monitor_loop(self) -> None:
        """Main monitoring loop for orders, permits, and deadlines."""
        # Initial snapshot (don't alert on first run)
        await self._take_initial_snapshot()

        while self._running:
            try:
                await asyncio.sleep(self.poll_interval)
                if not self._running:
                    break

                await self._check_order_status_changes()
                await self._check_new_order_assignments()
                await self._check_permit_expirations()
                await self._check_delivery_deadlines()
                self.clear_old_alerts()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in proactive monitor loop: %s", e)
                await asyncio.sleep(10)

    async def _weather_loop(self) -> None:
        """Weather monitoring loop (runs less frequently)."""
        # Wait a bit before first weather check
        await asyncio.sleep(30)

        while self._running:
            try:
                await self._check_route_weather()
                await asyncio.sleep(self.weather_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in weather monitor loop: %s", e)
                await asyncio.sleep(60)

    # ─── Initial Snapshot ─────────────────────────────────────────────────

    async def _take_initial_snapshot(self) -> None:
        """Capture current state so first cycle doesn't generate false alerts."""
        try:
            order_ids = self._get_user_order_ids()
            self._last_order_ids = set(order_ids)

            db = get_db()
            for oid in order_ids:
                doc = db.orders.find_one({"id": oid})
                if doc:
                    status = self._extract_order_status(doc)
                    self._last_order_statuses[oid] = status

            logger.info(
                "Proactive monitor: initial snapshot of %d orders",
                len(order_ids),
            )
        except Exception as e:
            logger.error("Error taking initial snapshot: %s", e)

    # ─── Order Status Changes ─────────────────────────────────────────────

    async def _check_order_status_changes(self) -> None:
        """Detect and alert on order status changes."""
        try:
            db = get_db()
            order_ids = self._get_user_order_ids()

            for oid in order_ids:
                doc = db.orders.find_one({"id": oid})
                if not doc:
                    continue

                current_status = self._extract_order_status(doc)
                previous_status = self._last_order_statuses.get(oid)

                if previous_status and current_status != previous_status:
                    alert = ProactiveAlert(
                        alert_type="order_status",
                        priority=AlertPriority.HIGH,
                        title=f"Order {oid} status changed",
                        message=(
                            f"Heads up! Order {oid} status has changed "
                            f"from {previous_status} to {current_status}."
                        ),
                        order_id=oid,
                        metadata={
                            "old_status": previous_status,
                            "new_status": current_status,
                        },
                    )
                    self._enqueue_alert(alert)

                self._last_order_statuses[oid] = current_status

        except Exception as e:
            logger.error("Error checking order status changes: %s", e)

    # ─── New Order Assignments ────────────────────────────────────────────

    async def _check_new_order_assignments(self) -> None:
        """Detect newly assigned orders for the user."""
        try:
            current_order_ids = set(self._get_user_order_ids())
            new_ids = current_order_ids - self._last_order_ids

            for oid in new_ids:
                alert = ProactiveAlert(
                    alert_type="new_order",
                    priority=AlertPriority.MEDIUM,
                    title=f"New order {oid} assigned",
                    message=(
                        f"You have a new order assignment! "
                        f"Order {oid} has been assigned to you. "
                        f"Would you like me to show you the details?"
                    ),
                    order_id=oid,
                )
                self._enqueue_alert(alert)

            self._last_order_ids = current_order_ids

        except Exception as e:
            logger.error("Error checking new order assignments: %s", e)

    # ─── Permit Expirations ───────────────────────────────────────────────

    async def _check_permit_expirations(self) -> None:
        """Alert on permits nearing or past expiration."""
        try:
            db = get_db()
            order_ids = self._get_user_order_ids()
            now = datetime.now()

            for oid in order_ids:
                doc = db.orders.find_one({"id": oid})
                if not doc:
                    continue

                route_data = doc.get("order", {}).get("routeData", [])
                if not isinstance(route_data, list):
                    continue

                for state_entry in route_data:
                    state_name = state_entry.get("product_name", "Unknown")
                    permit_key = f"{oid}_{state_name}"

                    if permit_key in self._warned_permits:
                        continue

                    # Check permit expiry from attached_at or other date fields
                    attached_at = state_entry.get("attached_at")
                    permit_status = state_entry.get("permit_status", "")

                    # Check if permit has an expiry indicator
                    if attached_at:
                        try:
                            attach_date = self._parse_date(attached_at)
                            if attach_date:
                                # Typical permits valid for 5-10 days
                                estimated_expiry = attach_date + timedelta(days=7)
                                days_until_expiry = (estimated_expiry - now).days

                                if days_until_expiry < 0:
                                    alert = ProactiveAlert(
                                        alert_type="permit_expired",
                                        priority=AlertPriority.CRITICAL,
                                        title=f"Permit expired: {state_name}",
                                        message=(
                                            f"Alert! The permit for {state_name} "
                                            f"on order {oid} appears to have expired "
                                            f"{abs(days_until_expiry)} days ago. "
                                            f"Please verify and renew if needed."
                                        ),
                                        order_id=oid,
                                        metadata={
                                            "state": state_name,
                                            "days_expired": abs(days_until_expiry),
                                        },
                                    )
                                    self._enqueue_alert(alert)
                                    self._warned_permits.add(permit_key)

                                elif days_until_expiry <= self.permit_warning_days:
                                    alert = ProactiveAlert(
                                        alert_type="permit_expiring",
                                        priority=AlertPriority.HIGH,
                                        title=f"Permit expiring: {state_name}",
                                        message=(
                                            f"Reminder: The permit for {state_name} "
                                            f"on order {oid} is expiring in "
                                            f"{days_until_expiry} day{'s' if days_until_expiry != 1 else ''}. "
                                            f"Please ensure it's renewed on time."
                                        ),
                                        order_id=oid,
                                        metadata={
                                            "state": state_name,
                                            "days_remaining": days_until_expiry,
                                        },
                                    )
                                    self._enqueue_alert(alert)
                                    self._warned_permits.add(permit_key)
                        except Exception:
                            pass

                    # Also alert if permit status indicates an issue
                    if permit_status and permit_status.lower() in (
                        "expired",
                        "rejected",
                        "cancelled",
                    ):
                        if permit_key not in self._warned_permits:
                            alert = ProactiveAlert(
                                alert_type="permit_issue",
                                priority=AlertPriority.CRITICAL,
                                title=f"Permit issue: {state_name}",
                                message=(
                                    f"Alert! The permit for {state_name} on order "
                                    f"{oid} has status: {permit_status}. "
                                    f"This needs immediate attention."
                                ),
                                order_id=oid,
                                metadata={
                                    "state": state_name,
                                    "status": permit_status,
                                },
                            )
                            self._enqueue_alert(alert)
                            self._warned_permits.add(permit_key)

        except Exception as e:
            logger.error("Error checking permit expirations: %s", e)

    # ─── Delivery Deadlines ───────────────────────────────────────────────

    async def _check_delivery_deadlines(self) -> None:
        """Alert on deliveries with approaching deadlines."""
        try:
            db = get_db()
            order_ids = self._get_user_order_ids()
            now = datetime.now()

            for oid in order_ids:
                if oid in self._warned_deadlines:
                    continue

                doc = db.orders.find_one({"id": oid})
                if not doc:
                    continue

                order_data = doc.get("order", {})

                # Check various date fields that might indicate deadlines
                for date_field in ("delivery_date", "end_date", "estimated_delivery"):
                    date_val = order_data.get(date_field)
                    if not date_val:
                        continue

                    deadline = self._parse_date(date_val)
                    if not deadline:
                        continue

                    hours_remaining = (deadline - now).total_seconds() / 3600

                    if 0 < hours_remaining <= self.deadline_warning_hours:
                        hours_int = int(hours_remaining)
                        alert = ProactiveAlert(
                            alert_type="deadline_approaching",
                            priority=AlertPriority.HIGH,
                            title=f"Deadline: Order {oid}",
                            message=(
                                f"Reminder: Order {oid} has a delivery deadline "
                                f"in approximately {hours_int} hours. "
                                f"Scheduled for {deadline.strftime('%B %d at %I:%M %p')}."
                            ),
                            order_id=oid,
                            metadata={
                                "deadline": deadline.isoformat(),
                                "hours_remaining": hours_int,
                            },
                        )
                        self._enqueue_alert(alert)
                        self._warned_deadlines.add(oid)
                        break  # One deadline alert per order

                    elif hours_remaining <= 0:
                        # Overdue
                        status = self._extract_order_status(doc)
                        if status and status.lower() not in (
                            "completed",
                            "delivered",
                            "closed",
                        ):
                            alert = ProactiveAlert(
                                alert_type="deadline_overdue",
                                priority=AlertPriority.CRITICAL,
                                title=f"Overdue: Order {oid}",
                                message=(
                                    f"Alert! Order {oid} appears to be overdue. "
                                    f"The deadline was {deadline.strftime('%B %d at %I:%M %p')}. "
                                    f"Current status: {status}."
                                ),
                                order_id=oid,
                                metadata={
                                    "deadline": deadline.isoformat(),
                                    "status": status,
                                },
                            )
                            self._enqueue_alert(alert)
                            self._warned_deadlines.add(oid)
                            break

        except Exception as e:
            logger.error("Error checking delivery deadlines: %s", e)

    # ─── Route Weather ────────────────────────────────────────────────────

    async def _check_route_weather(self) -> None:
        """Check for severe weather along active order routes."""
        try:
            db = get_db()
            order_ids = self._get_user_order_ids()

            for oid in order_ids:
                doc = db.orders.find_one({"id": oid})
                if not doc:
                    continue

                # Only check open/active orders
                status = self._extract_order_status(doc)
                if status and status.lower() in ("completed", "delivered", "closed", "cancelled"):
                    continue

                order_data = doc.get("order", {})

                # Extract route cities from origin/destination or route data
                cities = set()
                for field_name in ("origin_city", "pickup_city", "from_city"):
                    city = order_data.get(field_name)
                    if city and isinstance(city, str):
                        cities.add(city.strip())

                for field_name in ("destination_city", "delivery_city", "to_city"):
                    city = order_data.get(field_name)
                    if city and isinstance(city, str):
                        cities.add(city.strip())

                # Also check route states for major cities
                route_data = order_data.get("routeData", [])
                if isinstance(route_data, list):
                    for state_entry in route_data:
                        state_name = state_entry.get("product_name", "")
                        if state_name:
                            cities.add(state_name)

                # Check weather for each unique city
                for city in cities:
                    weather_key = f"weather_{oid}_{city}"
                    if weather_key in self._delivered_keys:
                        continue

                    try:
                        weather_info = get_weather_by_city(city)
                        if weather_info and self._is_severe_weather(weather_info):
                            alert = ProactiveAlert(
                                alert_type="weather_alert",
                                priority=AlertPriority.CRITICAL,
                                title=f"Severe weather: {city}",
                                message=(
                                    f"Weather alert for your route! "
                                    f"Severe conditions detected near {city} "
                                    f"on order {oid}. {weather_info} "
                                    f"Please exercise caution."
                                ),
                                order_id=oid,
                                metadata={
                                    "city": city,
                                    "weather": weather_info,
                                },
                            )
                            self._enqueue_alert(alert)
                            self._delivered_keys.add(weather_key)
                    except Exception:
                        pass  # Weather API failures shouldn't crash monitoring

        except Exception as e:
            logger.error("Error checking route weather: %s", e)

    # ─── Helper Methods ───────────────────────────────────────────────────

    def _get_user_order_ids(self) -> List[int]:
        """Get the list of order IDs for the current user."""
        try:
            db = get_db()

            if self.user_role == "admin":
                # Admins: return limited recent orders
                cursor = (
                    db.orders.find({}, {"id": 1})
                    .sort("id", -1)
                    .limit(20)
                )
                return [doc["id"] for doc in cursor if "id" in doc]

            elif self.user_role == "driver":
                user_doc = db.drivers.find_one({"email": self.user_email})
                return user_doc.get("order_ids", []) if user_doc else []

            elif self.user_role == "client":
                user_doc = db.clients.find_one({"email": self.user_email})
                return user_doc.get("order_ids", []) if user_doc else []

            return []

        except Exception as e:
            logger.error("Error getting user order IDs: %s", e)
            return []

    def _extract_order_status(self, doc: Dict[str, Any]) -> str:
        """Extract the status string from an order document."""
        order_data = doc.get("order", {})
        for status_field in ("status", "order_status", "orderStatus", "state"):
            val = order_data.get(status_field)
            if val and isinstance(val, str):
                return val
        return "unknown"

    def _parse_date(self, date_val: Any) -> Optional[datetime]:
        """Try to parse a date value from various formats."""
        if isinstance(date_val, datetime):
            return date_val

        if not isinstance(date_val, str):
            return None

        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%m/%d/%Y %H:%M:%S",
            "%d-%m-%Y",
            "%B %d, %Y",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_val, fmt)
            except ValueError:
                continue

        return None

    def _is_severe_weather(self, weather_info: str) -> bool:
        """Check if a weather description indicates severe conditions."""
        severe_keywords = (
            "storm", "thunderstorm", "tornado", "hurricane",
            "blizzard", "heavy rain", "heavy snow", "ice",
            "freezing rain", "hail", "flood", "warning",
            "extreme", "severe", "dangerous", "advisory",
            "high wind", "gale", "fog",
        )
        info_lower = weather_info.lower()
        return any(keyword in info_lower for keyword in severe_keywords)

    def _alert_key(self, alert: ProactiveAlert) -> str:
        """Generate a deduplication key for an alert."""
        return f"{alert.alert_type}_{alert.order_id}_{alert.title}"

    def _enqueue_alert(self, alert: ProactiveAlert) -> None:
        """Add an alert to the queue if not already delivered."""
        key = self._alert_key(alert)
        if key not in self._delivered_keys:
            self.alert_queue.append(alert)
            logger.info(
                "Proactive alert queued: [%s] %s",
                alert.priority.name,
                alert.title,
            )

    # ─── Summary Generation ───────────────────────────────────────────────

    async def generate_proactive_summary(self) -> Optional[str]:
        """Use LLM to generate a natural-sounding summary of pending alerts.

        Returns:
            A concise spoken summary, or None if no alerts.
        """
        pending = self.get_pending_alerts()
        if not pending:
            return None

        # Build alert descriptions for the LLM
        alert_descriptions = []
        for i, alert in enumerate(pending[:5], 1):  # Max 5 alerts at a time
            alert_descriptions.append(
                f"{i}. [{alert.priority.name}] {alert.message}"
            )

        alerts_text = "\n".join(alert_descriptions)

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a proactive voice assistant for heavy haul logistics. "
                    "Summarize the following alerts into a brief, natural spoken notification. "
                    "Prioritize critical alerts. Keep it concise — under 3 sentences if possible. "
                    "Start with 'I have an update for you.' or similar attention-getting phrase. "
                    "Do not use bullet points or formatting — this will be spoken aloud."
                ),
            },
            {
                "role": "user",
                "content": f"Summarize these alerts for the {self.user_role}:\n{alerts_text}",
            },
        ]

        try:
            llm = get_llm()
            summary = llm.chat(messages, max_tokens=200)
            return summary.strip() if summary else None
        except Exception as e:
            logger.error("Error generating proactive summary: %s", e)
            # Fallback: return the highest priority alert directly
            if pending:
                return pending[0].message
            return None
