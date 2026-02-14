"""
State information service for HeavyHaul AI.

Handles queries about US/Canadian state regulations, provisions,
and legal requirements for heavy haul transportation.
"""

import asyncio
import logging
from typing import Optional

from config.constants import (
    ORDER_SWITCH_KEYWORDS,
    PERMIT_SWITCH_KEYWORDS,
    PROVISION_KEYWORDS,
    STATES,
)
from config.settings import settings
from db import get_db
from services.llm_client import get_llm
from services.speech_service import SpeechSynthesizer, take_command
from utils.text import split_sentences

logger = logging.getLogger(__name__)


def find_state_in_query(query: str) -> Optional[str]:
    """Detect a state name mentioned in a query.

    Args:
        query: The user's query text.

    Returns:
        The matched state name, or None.
    """
    query_lower = query.lower()
    for state in STATES:
        if state.lower() in query_lower:
            return state
    return None


def _should_switch_to_orders(query: str) -> bool:
    """Check if the query indicates switching to order system.

    Args:
        query: The user's query text.

    Returns:
        True if the query contains order-switching keywords.
    """
    query_lower = query.lower()
    return any(keyword in query_lower for keyword in ORDER_SWITCH_KEYWORDS)


async def get_state_info(
    speech_synthesizer: SpeechSynthesizer,
    query: Optional[str] = None,
) -> str:
    """Interactive state information Q&A loop.

    Allows users to ask questions about state regulations, with
    the ability to switch back to orders or permits.

    Args:
        speech_synthesizer: TTS engine for spoken responses.
        query: Initial query (skips first listen if provided).

    Returns:
        The system to switch to: 'states', 'orders', or 'permits'.
    """
    db = get_db()
    llm = get_llm()
    states_collection = db.states
    current_state: Optional[str] = None

    while True:
        if query is None:
            print("\nListening for your question...")
            query = await take_command()

        if query.lower() in ("quit", "exit", "none"):
            break

        # Check for system switching
        if _should_switch_to_orders(query):
            await speech_synthesizer.text_to_speech("Switching back to order system...")
            return "orders"

        if any(kw in query.lower() for kw in PERMIT_SWITCH_KEYWORDS):
            return "permits"

        # Detect state in query
        state_in_query = find_state_in_query(query)
        if state_in_query:
            current_state = state_in_query

        if current_state is None:
            response = "Please mention a valid state name in your question."
            await speech_synthesizer.text_to_speech(response)
            print(response)
            query = None
            continue

        # Fetch state data from MongoDB
        state_doc = states_collection.find_one(
            {"state_name": {"$regex": f"^{current_state}$", "$options": "i"}}
        )

        if not state_doc:
            response = "State not found in database. Please try another state."
            await speech_synthesizer.text_to_speech(response)
            print(response)
            current_state = None
            query = None
            continue

        # Prepare context (exclude internal fields)
        state_info = state_doc.get("info", {})
        state_info.pop("others", None)
        state_info.pop("provision_info", None)

        prompt = (
            f"Based on this information about {current_state}: "
            f"State Information: {state_info}\n\n"
            f"Question: {query}\n"
            f"(Response should be short, relevant to the question)."
        )

        await speech_synthesizer.text_to_speech("Let me check that information for you.")
        print("\nResponse: ", end="", flush=True)

        try:
            messages = [{"role": "user", "content": prompt}]
            stream = llm.stream_chat(
                messages,
                model=settings.llm.groq_fast_model,
                temperature=0.2,
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

            speech_synthesizer.wait_for_playback_completion()
            print("\n")

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            logger.error(error_msg)
            await speech_synthesizer.text_to_speech(error_msg)

        query = None

    return "states"
