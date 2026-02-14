"""
Core AI assistant brain for HeavyHaul AI.

Orchestrates query routing, LLM response generation, order context
management, and system switching between orders, permits, and states.
"""

import json
import logging
import re
from typing import Any, Dict, Optional, Tuple

from config.constants import (
    ORDER_SWITCH_KEYWORDS,
    PERMIT_SWITCH_KEYWORDS,
    PROVISION_KEYWORDS,
    ROLE_SYSTEM_PROMPTS,
)
from config.settings import settings
from services.llm_client import get_llm
from services.order_cache import OrderCache
from services.order_service import get_order_details, resolve_order_context
from services.permit_service import chat_with_permit_info
from services.speech_service import SpeechSynthesizer
from services.state_service import get_state_info
from services.user_service import get_user_info
from utils.data import remove_deleted_permits, remove_null_fields
from utils.text import normalize_whitespace, split_sentences

logger = logging.getLogger(__name__)


async def generate_response(
    query: str,
    user_email: str,
    order_cache: OrderCache,
    role: str,
    speech_synthesizer: SpeechSynthesizer,
) -> str:
    """Generate an AI response for an order-related query.

    Resolves order context, fetches relevant data, and streams
    an LLM response with sentence-by-sentence TTS playback.

    Args:
        query: The user's natural language query.
        user_email: The authenticated user's email.
        order_cache: Order caching service instance.
        role: User role ('driver', 'client', 'admin').
        speech_synthesizer: TTS engine for spoken output.

    Returns:
        Empty string on success (response already printed/spoken),
        or error message string.
    """
    try:
        # Get user data
        user_data = get_user_info(role, user_email)
        if "error" in user_data:
            return user_data["error"]

        # Resolve which order to use
        should_switch, relevant_order_ids, explanation = resolve_order_context(
            query, order_cache.current_order_id, user_data
        )

        if should_switch or order_cache.current_order_id is None:
            if relevant_order_ids:
                new_order_id = relevant_order_ids[0]

                # Try cache first
                cached_details, cached_explanation = order_cache.load(
                    new_order_id, role
                )
                if cached_details is not None:
                    order_details = cached_details
                else:
                    order_details = get_order_details(relevant_order_ids, role)
                    if order_details:
                        order_cache.set_current_order(
                            new_order_id, order_details, explanation, role
                        )
                    else:
                        return "Sorry, couldn't fetch order details from the database."

                order_cache.current_order_id = new_order_id
                order_cache.current_details = order_details
                order_cache.explanation = explanation

        if not order_cache.current_details:
            return "Sorry, no order details are currently available."

        # Build system message
        sys_msg = ROLE_SYSTEM_PROMPTS.get(role, ROLE_SYSTEM_PROMPTS["admin"])

        # Extract order counts
        role_key = f"{role}_info"
        open_close_orders = user_data.get(role_key, {}).get("Open_Close Orders", {})
        open_count = len(open_close_orders.get("open_orders", []))
        closed_count = len(open_close_orders.get("closed_orders", []))

        # Clean order details
        filtered_details = remove_null_fields(order_cache.current_details)
        if (
            filtered_details
            and "routeData" in filtered_details[0].get("Order Details", {})
        ):
            filtered_details[0]["Order Details"]["routeData"] = (
                remove_deleted_permits(
                    filtered_details[0]["Order Details"]["routeData"]
                )
            )

        # Build user message
        user_message = normalize_whitespace(
            f"Query: {query}, "
            f"Order Selection: {order_cache.explanation}, "
            f"{open_close_orders}, "
            f"OpenOrdersCount: {open_count}, "
            f"Closed/Completed OrdersCount: {closed_count}, "
            f"Available Order Details: {json.dumps(filtered_details, indent=2)}, "
            "Provide a direct and short answer using only the information "
            "from the specified order. Put '.' at last if a sentence."
        )

        messages = [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": user_message},
        ]

        # Stream LLM response
        llm = get_llm()
        stream = llm.stream_chat(messages)

        response = ""
        buffer = ""

        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content is not None:
                print(content, end="", flush=True)
                response += content
                buffer += content

                # Flush buffer at sentence boundaries
                if any(buffer.endswith(p) for p in (".", ":")):
                    if buffer.endswith(".") and len(buffer) > 1 and buffer[-2].isdigit():
                        continue
                    await speech_synthesizer.text_to_speech(buffer)
                    buffer = ""

        if buffer.strip():
            await speech_synthesizer.text_to_speech(buffer)

        speech_synthesizer.wait_for_playback_completion()
        print()
        return ""

    except Exception as e:
        logger.error("Error generating response: %s", e)
        return "Sorry, I encountered an error while processing your request."


async def handle_query(
    query: str,
    user_email: str,
    order_cache: OrderCache,
    user_role: str,
    speech_synthesizer: SpeechSynthesizer,
) -> Tuple[str, str]:
    """Route a query to the appropriate subsystem.

    Detects intent (orders, permits, states) and delegates
    to the correct handler.

    Args:
        query: The user's natural language query.
        user_email: The authenticated user's email.
        order_cache: Order caching service instance.
        user_role: User role string.
        speech_synthesizer: TTS engine.

    Returns:
        Tuple of (response_text, system_name).
    """
    query_lower = query.lower()

    # Check for provision/state system switch
    if any(kw in query_lower for kw in PROVISION_KEYWORDS):
        await speech_synthesizer.text_to_speech("Switching to State Information System...")
        result = await get_state_info(speech_synthesizer, query)
        return "", result

    # Check for permit system switch
    if any(kw in query_lower for kw in PERMIT_SWITCH_KEYWORDS):
        if order_cache.current_order_id:
            await speech_synthesizer.text_to_speech("Switching to Permit System...")
            result = await chat_with_permit_info(
                order_cache.current_order_id, speech_synthesizer
            )
            return "", result
        else:
            await speech_synthesizer.text_to_speech(
                "Please select an order first before checking permits."
            )
            return "", "orders"

    # Check for explicit order system switch
    if any(kw in query_lower for kw in ORDER_SWITCH_KEYWORDS):
        await speech_synthesizer.text_to_speech("Switching to Orders...")
        return "", "orders"

    # Default: handle as order query
    response = await generate_response(
        query, user_email, order_cache, user_role, speech_synthesizer
    )
    return response, "orders"
