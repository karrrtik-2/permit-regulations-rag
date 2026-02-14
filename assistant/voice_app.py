"""
Voice assistant entry point for HeavyHaul AI.

Provides the main interactive loop with voice input/output,
wake word detection, system routing, and proactive notifications.
"""

import asyncio
import logging
from datetime import datetime

from assistant import handle_query
from config.constants import PROACTIVE_STATUS_KEYWORDS
from config.settings import settings
from services.conversation import ConversationHandler
from services.location_weather import (
    get_location_string,
    get_weather,
    get_weather_by_city,
)
from services.order_cache import OrderCache
from services.proactive_monitor import ProactiveMonitor
from services.speech_service import SpeechSynthesizer, take_command
from services.user_service import VALID_ROLES, verify_email

logger = logging.getLogger(__name__)

# Module-level state
conversation_handler = ConversationHandler()
user_role: str = ""
user_email: str = ""
order_cache: OrderCache = OrderCache()
speech_synthesizer: SpeechSynthesizer = None  # type: ignore
proactive_monitor: ProactiveMonitor = None  # type: ignore


async def initialize_user() -> None:
    """Set up the user session with role, email verification, and proactive monitoring."""
    global user_role, user_email, order_cache, speech_synthesizer, proactive_monitor

    order_cache = OrderCache()
    speech_synthesizer = SpeechSynthesizer()

    # Get role via text input
    while True:
        role = input("Please enter your role (Admin/Client/Driver): ").strip().lower()
        if role in VALID_ROLES:
            user_role = role
            break
        print("Invalid role. Please enter Admin, Client, or Driver.")

    print(f"\nRole set as: {user_role.capitalize()}")

    # Get email for non-admin roles
    if user_role in ("driver", "client"):
        while True:
            email = input(f"Please provide your email ID ({user_role}): ").strip()
            if email and verify_email(user_role, email):
                user_email = email
                break
            print(f"Email not found. Please provide a valid email ID.")
        print(f"\nEmail verified for {user_role}: {user_email}")
    else:
        user_email = "admin"
        print("\nAdmin mode: Access any order by mentioning its ID")
        print("Example: 'Show me order 2892' or 'Tell me about #2892'\n")

    # Start proactive monitoring
    if settings.proactive.enabled:
        proactive_monitor = ProactiveMonitor(
            user_role=user_role,
            user_email=user_email,
            poll_interval=settings.proactive.poll_interval,
            weather_interval=settings.proactive.weather_interval,
            permit_warning_days=settings.proactive.permit_warning_days,
            deadline_warning_hours=settings.proactive.deadline_warning_hours,
        )
        proactive_monitor.start()
        logger.info("Proactive monitoring enabled")

    await speech_synthesizer.text_to_speech(
        f"Welcome {user_role}, I'm ready to assist you"
    )


async def greet() -> None:
    """Deliver a time-appropriate greeting."""
    hour = datetime.now().hour
    if 6 <= hour < 12:
        greeting = "Good morning Sir, How may I assist you?"
    elif 12 <= hour < 16:
        greeting = "Good afternoon Sir, How may I assist you?"
    elif 16 <= hour < 21:
        greeting = "Good evening Sir, How may I assist you?"
    else:
        greeting = "Hello Sir, How may I assist you?"

    await speech_synthesizer.text_to_speech(greeting)


async def process_command(query: str) -> None:
    """Process a single user command.

    Routes to weather, location, proactive updates, exit, or AI query handling.

    Args:
        query: The preprocessed user query text.
    """
    query_lower = query.lower()

    # Exit command
    if "ok bye" in query_lower:
        hour = datetime.now().hour
        farewell = (
            "Good night sir, take care!"
            if hour >= 21 or hour < 6
            else "Have a good day sir!"
        )
        print("Assistant:", farewell)
        await speech_synthesizer.text_to_speech(farewell)
        conversation_handler.save(query, farewell)
        if proactive_monitor:
            proactive_monitor.stop()
        exit()

    # Proactive status check ("any updates?", "any alerts?", "what's new?")
    elif any(kw in query_lower for kw in PROACTIVE_STATUS_KEYWORDS):
        await _deliver_proactive_alerts(force=True)

    # Location query
    elif any(
        phrase in query_lower
        for phrase in ("where am i", "my location", "current location")
    ):
        location_info = get_location_string()
        print(location_info)
        await speech_synthesizer.text_to_speech(location_info)
        conversation_handler.save(query, location_info)

    # City-specific weather query
    elif "weather of" in query_lower or "weather in" in query_lower:
        separator = "weather of" if "weather of" in query_lower else "weather in"
        city_name = query_lower.split(separator)[-1].strip()

        if city_name:
            await speech_synthesizer.text_to_speech(
                f"Checking the weather in {city_name}."
            )
            weather_info = get_weather_by_city(city_name)
            print(weather_info)
            await speech_synthesizer.text_to_speech(weather_info)
            conversation_handler.save(query, weather_info)
        else:
            await speech_synthesizer.text_to_speech(
                "Please specify a city for the weather information."
            )

    # General weather query
    elif any(
        phrase in query_lower
        for phrase in ("weather", "temperature", "how hot", "how cold")
    ):
        weather_info = get_weather()
        print(weather_info)
        await speech_synthesizer.text_to_speech(weather_info)
        conversation_handler.save(query, weather_info)

    # AI query (orders, permits, states)
    else:
        try:
            response, system = await handle_query(
                query, user_email, order_cache, user_role, speech_synthesizer
            )

            if response:
                print("Assistant:", response)
                await speech_synthesizer.text_to_speech(response)
                conversation_handler.save(query, response)

            if system == "exit":
                await speech_synthesizer.text_to_speech("Goodbye!")
                exit()

        except Exception as e:
            error_msg = f"Sorry, I encountered an error: {str(e)}"
            logger.error(error_msg)
            print(error_msg)
            await speech_synthesizer.text_to_speech(error_msg)
            conversation_handler.save(query, error_msg)


async def _deliver_proactive_alerts(force: bool = False) -> None:
    """Deliver pending proactive alerts to the user via TTS.

    Args:
        force: If True, deliver even if no alerts (says "no updates").
    """
    if not proactive_monitor:
        if force:
            await speech_synthesizer.text_to_speech(
                "Proactive monitoring is not enabled."
            )
        return

    if not proactive_monitor.has_alerts:
        if force:
            await speech_synthesizer.text_to_speech(
                "No new updates or alerts at the moment. Everything looks good."
            )
            conversation_handler.save("Status check", "No new updates.")
        return

    # Generate a natural summary using the LLM
    summary = await proactive_monitor.generate_proactive_summary()

    if summary:
        print(f"\n🔔 Proactive Alert: {summary}")
        await speech_synthesizer.text_to_speech(summary)
        conversation_handler.save("Proactive notification", summary)

        # Mark all delivered alerts
        for alert in proactive_monitor.get_pending_alerts():
            proactive_monitor.mark_delivered(alert)
    elif force:
        await speech_synthesizer.text_to_speech(
            "No new updates or alerts at the moment."
        )


async def main() -> None:
    """Main voice assistant loop with wake word detection and proactive alerts."""
    global speech_synthesizer

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    speech_synthesizer = SpeechSynthesizer()
    conversation_handler.clear()
    await initialize_user()
    await greet()

    # Track time since last proactive check
    last_proactive_check = datetime.now()
    alert_check_interval = (
        settings.proactive.alert_check_interval
        if settings.proactive.enabled
        else 9999
    )

    while True:
        try:
            # Check for proactive alerts between interactions
            if (
                proactive_monitor
                and settings.proactive.enabled
                and (datetime.now() - last_proactive_check).total_seconds()
                >= alert_check_interval
            ):
                await _deliver_proactive_alerts()
                last_proactive_check = datetime.now()

            query = await take_command()
            if query == "none":
                continue

            words = query.split()
            if words and words[0] in settings.wake_words:
                processed = " ".join(words[1:])
                if processed:
                    await process_command(processed)
                else:
                    response = "Yes, how can I help you?"
                    await speech_synthesizer.text_to_speech(response)
                    conversation_handler.save("Wake word detected", response)
            else:
                # Process without wake word requirement
                await process_command(query)

        except KeyboardInterrupt:
            print("\nExiting...")
            if proactive_monitor:
                proactive_monitor.stop()
            break
        except Exception as e:
            logger.error("Error in main loop: %s", e)
            await speech_synthesizer.text_to_speech(
                "Sorry, I encountered an error. Please try again."
            )


if __name__ == "__main__":
    asyncio.run(main())
