import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


class ConversationHandler:
    """Manages conversation history persistence.

    Stores timestamped user/assistant exchanges to a text file
    and maintains an in-memory copy for context.
    """

    def __init__(self, filename: str = "data/conversation_log.txt") -> None:
        """Initialize the conversation handler.

        Args:
            filename: Path to the conversation log file.
        """
        self.filename = filename
        self.conversation_history: str = ""

        # Ensure data directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        self.clear()

    def save(self, query: str, response: str) -> None:
        """Save a conversation exchange.

        Args:
            query: The user's input.
            response: The assistant's response.
        """
        try:
            with open(self.filename, "a", encoding="utf-8") as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{timestamp}]\n")
                f.write(f"User: {query}\n")
                f.write(f"Assistant: {response}\n\n")
            self._load()
        except Exception as e:
            logger.error("Error saving conversation: %s", e)

    def clear(self) -> None:
        """Clear all conversation history."""
        try:
            if os.path.exists(self.filename):
                os.remove(self.filename)
            self.conversation_history = ""
        except Exception as e:
            logger.error("Error clearing conversation history: %s", e)

    def _load(self) -> str:
        """Load conversation history from file.

        Returns:
            The full conversation history text.
        """
        try:
            if os.path.exists(self.filename):
                with open(self.filename, "r", encoding="utf-8") as f:
                    self.conversation_history = f.read()
            return self.conversation_history
        except Exception as e:
            logger.error("Error loading conversation history: %s", e)
            return ""
