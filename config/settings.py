"""
Centralized configuration management for HeavyHaul AI.

All settings are loaded from environment variables with sensible defaults.
Use a .env file for local development.
"""

import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class MongoSettings:
    """MongoDB connection settings."""

    uri: str = field(default_factory=lambda: os.getenv("MONGO_URI", ""))
    database: str = field(default_factory=lambda: os.getenv("MONGO_DATABASE", "HeavyHaulDB"))

    # Collection names
    orders_collection: str = "All Orders"
    drivers_collection: str = "Drivers"
    clients_collection: str = "Clients"
    companies_collection: str = "Companies"
    states_collection: str = "All States"
    users_collection: str = "All Users"


@dataclass(frozen=True)
class LLMSettings:
    """LLM provider settings."""

    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    deep_infra_key: str = field(default_factory=lambda: os.getenv("DEEP_INFRA_KEY", ""))
    deep_infra_base_url: str = "https://api.deepinfra.com/v1/openai"
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_KEY", ""))

    # Model configurations
    groq_model: str = "llama-3.3-70b-versatile"
    groq_fast_model: str = "llama-3.3-70b-specdec"
    deep_infra_model: str = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
    embedding_model: str = "text-embedding-ada-002"

    # Generation parameters
    default_temperature: float = 0.3
    default_max_tokens: int = 300
    default_top_p: float = 1.0


@dataclass(frozen=True)
class SpeechSettings:
    """Speech synthesis and recognition settings."""

    tts_voice: str = field(
        default_factory=lambda: os.getenv("TTS_VOICE", "en-US-ChristopherNeural")
    )
    audio_frequency: int = 24000
    stream_audio_dir: str = "assets/stream_audios"
    recognizer_energy_threshold: int = 1000
    recognizer_pause_threshold: float = 1.0
    recognizer_phrase_threshold: float = 0.5
    recognizer_non_speaking_duration: float = 0.6
    listen_timeout: int = 5
    phrase_time_limit: int = 5


@dataclass(frozen=True)
class WeatherSettings:
    """Weather API settings."""

    api_key: str = field(default_factory=lambda: os.getenv("WEATHER_API_KEY", ""))
    base_url: str = "http://api.openweathermap.org/data/2.5/weather"
    units: str = "metric"


@dataclass(frozen=True)
class ETLSettings:
    """ETL pipeline settings."""

    api_base_url: str = field(
        default_factory=lambda: os.getenv(
            "ORDERS_API_BASE_URL", "https://permits.synchrontms.com/v1/orders/"
        )
    )
    user_api_url: str = field(
        default_factory=lambda: os.getenv(
            "USER_API_URL", "https://permits.synchrontms.com/v1/userrole/"
        )
    )
    states_api_url: str = field(
        default_factory=lambda: os.getenv(
            "STATES_API_URL", "https://synchrontms.com/api/v1/getstates"
        )
    )
    tesseract_cmd: str = field(
        default_factory=lambda: os.getenv(
            "TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        )
    )


@dataclass(frozen=True)
class RAGSettings:
    """RAG pipeline settings."""

    chroma_db_directory: str = "data/chroma_db"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    provision_topics: tuple = (
        "Night Travel or night restrictions",
        "Oversize Operating Time",
        "Speed limit or restrictions",
        "Restricted Travel",
        "Any weekend/holiday restrictions",
        "Curfew",
        "Escort",
        "Legal Dimensions or threshold dimensions",
        "Permit Limits or permit limitation",
        "Special Permit",
        "Superloads or overloads or oversize",
        "Signs or Flags",
        "Lights",
        "Weather Restrictions",
        "Miscellaneous",
    )


@dataclass(frozen=True)
class ProactiveSettings:
    """Proactive monitoring settings."""

    enabled: bool = field(
        default_factory=lambda: os.getenv("PROACTIVE_ENABLED", "true").lower() == "true"
    )
    poll_interval: int = field(
        default_factory=lambda: int(os.getenv("PROACTIVE_POLL_INTERVAL", "120"))
    )
    weather_interval: int = field(
        default_factory=lambda: int(os.getenv("PROACTIVE_WEATHER_INTERVAL", "1800"))
    )
    permit_warning_days: int = field(
        default_factory=lambda: int(os.getenv("PROACTIVE_PERMIT_WARNING_DAYS", "3"))
    )
    deadline_warning_hours: int = field(
        default_factory=lambda: int(os.getenv("PROACTIVE_DEADLINE_WARNING_HOURS", "24"))
    )
    alert_check_interval: int = field(
        default_factory=lambda: int(os.getenv("PROACTIVE_ALERT_CHECK_INTERVAL", "15"))
    )
    max_alerts_per_cycle: int = 5


@dataclass(frozen=True)
class AppSettings:
    """Root application settings container."""

    mongo: MongoSettings = field(default_factory=MongoSettings)
    llm: LLMSettings = field(default_factory=LLMSettings)
    speech: SpeechSettings = field(default_factory=SpeechSettings)
    weather: WeatherSettings = field(default_factory=WeatherSettings)
    etl: ETLSettings = field(default_factory=ETLSettings)
    rag: RAGSettings = field(default_factory=RAGSettings)
    proactive: ProactiveSettings = field(default_factory=ProactiveSettings)

    # Application-level settings
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    debug: bool = field(
        default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true"
    )
    wake_words: tuple = ("james", "pixel")

    def validate(self) -> list[str]:
        """Validate that required settings are present. Returns list of errors."""
        errors = []
        if not self.mongo.uri:
            errors.append("MONGO_URI environment variable is required")
        if not self.llm.groq_api_key:
            errors.append("GROQ_API_KEY environment variable is required")
        return errors


# Singleton settings instance
settings = AppSettings()
