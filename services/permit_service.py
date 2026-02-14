"""
Permit information service for HeavyHaul AI.

Handles queries about order-specific permit details,
including per-state permit Q&A with LLM assistance.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from config.constants import (
    ORDER_SWITCH_KEYWORDS,
    PERMIT_SYSTEM_PROMPT,
    PROVISION_KEYWORDS,
    STATES,
)
from config.settings import settings
from db import get_db
from services.llm_client import get_llm
from services.speech_service import SpeechSynthesizer, take_command
from utils.text import split_sentences

logger = logging.getLogger(__name__)


def get_state_permit_info(
    order_id: int, state_name: str
) -> Optional[Dict[str, Any]]:
    """Fetch permit information for a specific state within an order.

    Args:
        order_id: The order ID.
        state_name: The state name to look up permits for.

    Returns:
        Permit info dictionary, or None if not found.
    """
    try:
        order_id = int(order_id)
    except (ValueError, TypeError):
        return None

    db = get_db()
    order_doc = db.orders.find_one({"id": order_id})
    if not order_doc:
        return None

    order_data = order_doc.get("order", {})
    if not isinstance(order_data, dict):
        return None

    route_data = order_data.get("routeData", [])
    for state_obj in route_data:
        if state_obj.get("product_name", "").lower() == state_name.lower():
            permit_info = state_obj.get("permit_info", {})
            if permit_info:
                return permit_info

    return None


def extract_state_name(query: str) -> Optional[str]:
    """Extract a state name from a query, with fuzzy matching.

    Args:
        query: The user's query text.

    Returns:
        Matched state name, or None.
    """
    query_lower = query.lower()

    # Exact match
    for state in STATES:
        if state.lower() in query_lower:
            return state

    # No-space fuzzy match
    query_compact = query_lower.replace(" ", "")
    for state in STATES:
        if state.lower().replace(" ", "") in query_compact:
            return state

    return None


async def chat_with_permit_info(
    order_id: Optional[int] = None,
    speech_synthesizer: Optional[SpeechSynthesizer] = None,
) -> str:
    """Interactive permit information Q&A loop.

    Allows users to ask questions about permit details for
    specific states within an order.

    Args:
        order_id: The order to query permits for.
        speech_synthesizer: TTS engine. Created if not provided.

    Returns:
        The system to switch to: 'permits', 'orders', 'states', or 'exit'.
    """
    if speech_synthesizer is None:
        speech_synthesizer = SpeechSynthesizer()

    llm = get_llm()

    if order_id is None:
        await speech_synthesizer.text_to_speech("Please say the order ID")
        order_id_str = await take_command()
        try:
            order_id = int(order_id_str)
        except (ValueError, TypeError):
            await speech_synthesizer.text_to_speech("Invalid order ID.")
            return "orders"

    current_state: Optional[str] = None
    current_permit_info: Optional[Dict[str, Any]] = None

    try:
        await speech_synthesizer.text_to_speech(
            "What would you like to know about permits?"
        )

        while True:
            print("\nListening for your question...")
            user_query = await take_command()

            if user_query == "none":
                continue

            print(f"You asked: {user_query}")

            # Check for system switching
            if any(kw in user_query.lower() for kw in ORDER_SWITCH_KEYWORDS):
                await speech_synthesizer.text_to_speech("Switching back to order system")
                return "orders"

            if any(kw in user_query.lower() for kw in PROVISION_KEYWORDS):
                return "states"

            if user_query.lower() == "exit":
                return "exit"

            # Detect state change
            new_state = extract_state_name(user_query)
            if new_state and new_state != current_state:
                current_state = new_state
                current_permit_info = get_state_permit_info(order_id, current_state)

                if not current_permit_info:
                    msg = f"No permit information found for {current_state}."
                    print(msg)
                    await speech_synthesizer.text_to_speech(msg)
                    current_state = None
                    continue
                else:
                    msg = f"Switching to {current_state} permit information."
                    print(msg)
                    await speech_synthesizer.text_to_speech(msg)

            if not current_state:
                print("Please specify a state first.")
                continue

            # Build LLM messages
            system_message = (
                f"{PERMIT_SYSTEM_PROMPT}"
                f"Here is the permit information for {current_state}: "
                f"{current_permit_info}"
            )
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_query},
            ]

            try:
                stream = llm.stream_chat(
                    messages,
                    model=settings.llm.groq_fast_model,
                )

                buffer = ""
                for chunk in stream:
                    content = chunk.choices[0].delta.content
                    if content is not None:
                        print(content, end="", flush=True)
                        buffer += content

                if buffer.strip():
                    for sentence in split_sentences(buffer):
                        if sentence.strip():
                            await speech_synthesizer.text_to_speech(sentence)

                print("\n")

            except Exception as e:
                error_msg = f"Error generating response: {str(e)}"
                logger.error(error_msg)
                await speech_synthesizer.text_to_speech(error_msg)

    except Exception as e:
        logger.error("Permit chat error: %s", e)
        await speech_synthesizer.text_to_speech(f"An error occurred: {str(e)}")
        return "orders"

    return "permits"
