"""
Predefined constants, keyword lists, and state data for HeavyHaul AI.

Centralizes all magic strings, keyword triggers, and reference data
used across the application for intent detection and routing.
"""

from typing import Dict, FrozenSet, List, Set, Tuple

# ─── US & Canadian States / Provinces ────────────────────────────────────────

STATES: Tuple[str, ...] = (
    "Alabama", "Alaska", "Alberta", "Arizona", "Arkansas",
    "British Columbia", "California", "Colorado", "Connecticut",
    "Delaware", "Florida", "Georgia", "Hawaii", "Idaho",
    "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky",
    "Louisiana", "Maine", "Manitoba", "Maryland", "Massachusetts",
    "Michigan", "Minnesota", "Mississippi", "Missouri", "Montana",
    "Nebraska", "Nevada", "New Brunswick", "New Hampshire",
    "New Jersey", "New Mexico", "New York", "Newfoundland and Labrador",
    "North Carolina", "North Dakota", "Nova Scotia", "Ohio",
    "Oklahoma", "Ontario", "Oregon", "Pennsylvania",
    "Prince Edward Island", "Quebec", "Rhode Island", "Saskatchewan",
    "South Carolina", "South Dakota", "Tennessee", "Texas",
    "Utah", "Vermont", "Virginia", "Washington", "West Virginia",
    "Wisconsin", "Wyoming",
)

STATES_LOWER: Tuple[str, ...] = tuple(s.lower() for s in STATES)

# ─── Intent Detection Keywords ───────────────────────────────────────────────

ORDER_SWITCH_KEYWORDS: FrozenSet[str] = frozenset({
    "switch to orders", "go to orders", "go back to orders",
    "go back orders", "go back order", "check orders",
    "talk about orders", "discuss orders", "discuss about orders",
    "order system", "order management", "orders management",
    "orders updates", "order list", "orders list", "orders overview",
    "orders report", "orders data", "orders query", "orders search",
    "order inquiry", "orders inquiry", "order menu", "orders menu",
    "order section", "orders section", "order dashboard",
    "orders dashboard", "order portal", "orders portal",
    "order screen", "orders screen", "order page", "orders page",
    "order tab", "orders tab", "order module", "orders module",
    "order interface", "orders interface", "order platform",
    "orders platform", "show orders", "view orders",
    "return to orders",
})

PERMIT_SWITCH_KEYWORDS: FrozenSet[str] = frozenset({
    "switch to permit", "switch to permits",
    "go to permit", "go to permits",
    "go back to permit", "go back to permits",
    "go back permit", "go back permits",
    "open permit", "open permits",
    "see permit", "see permits",
    "show permit", "show permits",
    "view permit", "view permits",
    "check permit", "check permits",
    "talk about permit", "talk about permits",
    "discuss permit", "discuss permits",
    "discuss about permit", "discuss about permits",
    "permit system", "permits system",
    "permit management", "permits management",
    "permit updates", "permits updates",
    "permit list", "permits list",
    "permit overview", "permits overview",
    "permit report", "permits report",
    "permit data", "permits data",
    "permit query", "permits query",
    "permit search", "permits search",
    "permit inquiry", "permits inquiry",
    "permit menu", "permits menu",
    "permit section", "permits section",
    "permit dashboard", "permits dashboard",
    "permit portal", "permits portal",
    "permit screen", "permits screen",
    "permit page", "permits page",
    "permit tab", "permits tab",
    "permit module", "permits module",
    "permit interface", "permits interface",
    "permit platform", "permits platform",
})

PROVISION_KEYWORDS: FrozenSet[str] = frozenset({
    "provision", "state provision", "provision file",
    "provisional", "state provisional file", "provisional file",
    "provisions", "state info", "state information",
    "state data", "state details", "provision info",
    "provision information", "switch to states",
})

# ─── Route Data Keys ─────────────────────────────────────────────────────────

ROUTE_DATA_KEYS: FrozenSet[str] = frozenset({
    "permit_info", "price", "start_date", "use_tolls", "state_fee",
    "other_fee", "service_fee", "attached_at", "state_id",
    "permit_status", "permit_link", "route_image", "route_url_1",
    "state_name",
})

# ─── Date/Time Constants ─────────────────────────────────────────────────────

MONTHS: Tuple[str, ...] = (
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
)

PAST_30_DAYS_KEYWORDS: Tuple[str, ...] = (
    "this month", "week", "yesterday", "days",
)

LAST_N_MONTHS_KEYWORDS: Dict[str, int] = {
    "three": 3, "four": 4, "five": 5, "six": 6,
}

# ─── Order Position Mappings ─────────────────────────────────────────────────

POSITION_MAPPINGS: Dict[str, int] = {
    "third last": 2, "third latest": 2,
    "second last": 1, "second latest": 1,
    "fourth last": 3, "fourth latest": 3,
    "fifth last": 4, "fifth latest": 4,
    "sixth last": 5, "sixth latest": 5,
    "seventh last": 6, "seventh latest": 6,
    "eighth last": 7, "eighth latest": 7,
    "ninth last": 8, "ninth latest": 8,
    "tenth last": 9, "tenth latest": 9,
    "latest": 0, "last": 0, "newest": 0,
    "second": 1, "third": 2, "fourth": 3,
    "fifth": 4, "sixth": 5, "seventh": 6,
    "eighth": 7, "ninth": 8, "tenth": 9,
}

POSITION_DESCRIPTIONS: Dict[int, str] = {
    0: "latest", 1: "second latest", 2: "third latest",
    3: "fourth latest", 4: "fifth latest", 5: "sixth latest",
    6: "seventh latest", 7: "eighth latest", 8: "ninth latest",
    9: "tenth latest",
}

# ─── Role-Based Exclusion Fields ─────────────────────────────────────────────

COMMON_EXCLUDED_FIELDS: FrozenSet[str] = frozenset({
    "Company_attribute_Info", "state_webstie_detail",
    "transactions", "odOrderLogData", "meta",
})

META_EXCLUDED_FIELDS: FrozenSet[str] = frozenset({
    "permit_info", "meta_data", "truck_meta_data",
    "trailer_meta_data", "Company_meta_data",
    "client_meta_Data", "driver_meta_Data",
})

ADMIN_EXCLUDED_FIELDS: FrozenSet[str] = frozenset({
    "Company_attribute_Info", "state_webstie_detail",
    "odOrderLogData", "meta",
})

# ─── Prompt Templates ────────────────────────────────────────────────────────

INTENT_EXTRACTION_PROMPT: str = """You are a conversational voice assistant designed to extract specific information from user queries. Your task is to fill the following switches based on the user's query. Respond strictly with one word or "YES"/"NO" as specified. Do not provide any explanations, additional text, or context.

SWITCHES:
1. State name: (Fill with the state name if mentioned, otherwise leave blank.)
2. Order ID (if mentioned): (Fill with the order ID if mentioned, otherwise leave blank.)

3. Has mentioned any word about (reply in just YES or NO):
   - Open/Active/Live order:
   - Closed/Completed order:
   - Cancelled order:

4. Which order is it? (Fill with the number):
   - Last/latest order:
   - Second last order:
   - Third last order:

5. Month name: (Fill with the month name if mentioned, otherwise leave blank.)
6. Which month is it talking about? (Fill this: last ___ months) (if mentioned): (Provide a number if mentioned, otherwise leave blank.)

Rules:
- Fill only the relevant switches based on the user's query.
- Do not add any extra text, explanations, or formatting.
- Respond strictly with one word, "YES", "NO", or leave blank if not applicable."""

ROLE_SYSTEM_PROMPTS: Dict[str, str] = {
    "driver": (
        "You are an AI voice assistant for Truck Drivers. "
        "Provide direct and short answers about order details and driving instructions. "
        "Answer from the details provided wisely and response should be relevant to the query."
    ),
    "client": (
        "You are an AI assistant for Clients. "
        "Provide direct and short answers about order status and details. "
        "Answer from the details provided wisely and response should be relevant to the query."
    ),
    "admin": (
        "You are an AI assistant for Administrators. "
        "Provide comprehensive information about orders and system details. "
        "Answer from the details provided wisely and response should be relevant to the query."
    ),
}

PERMIT_SYSTEM_PROMPT: str = (
    "You are a helpful assistant that answers questions about permit information. "
    "Response should be short and to the point. "
    "When listing information in bullet points, end each point with a period. "
    "For example:\n"
    "- First point: value.\n"
    "- Second point: another value.\n"
)

PROACTIVE_SUMMARY_PROMPT: str = (
    "You are a proactive voice assistant for heavy haul logistics. "
    "Summarize the following alerts into a brief, natural spoken notification. "
    "Prioritize critical alerts. Keep it concise — under 3 sentences if possible. "
    "Start with 'I have an update for you.' or similar attention-getting phrase. "
    "Do not use bullet points or formatting — this will be spoken aloud."
)

PROACTIVE_STATUS_KEYWORDS: FrozenSet[str] = frozenset({
    "any updates", "any alerts", "any notifications",
    "what's new", "whats new", "anything new",
    "any changes", "status update", "status updates",
    "proactive update", "proactive updates",
    "check for updates", "check updates",
    "pending alerts", "any pending",
    "what did i miss", "anything i should know",
    "catch me up", "brief me",
})
