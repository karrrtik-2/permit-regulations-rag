# HeavyHaul AI

A Proactive Voice for **heavy-haul trucking logistics**, providing role-based order management, permit information, and state provision queries through natural conversation.

---

## Features

| Feature | Description |
|---|---|
| **Voice Assistant** | Wake-word activated speech interaction with TTS/STT |
| **Proactive Alerts** | Background monitoring for status changes, deadlines, permit issues, and route weather |
| **Role-Based Access** | Driver, Client, and Admin views with filtered data |
| **Order Management** | Natural language queries over MongoDB order data |
| **Permit Info** | State-specific permit Q&A with LLM streaming |
| **State Provisions** | RAG pipeline for state provision document search |
| **ETL Pipeline** | Automated order ingestion from external APIs |
| **Multi-LLM** | Groq (Llama 3.3 70B), DeepInfra, OpenAI, Gemini support |

---

## Architecture

```
config/           # Centralized settings & constants
├── settings.py   # Dataclass-based config from env vars
└── constants.py  # Keywords, states, prompts, field maps
db/               # MongoDB singleton connection
utils/            # Text processing & data cleaning
services/         # Business logic modules
├── llm_client.py         # Groq LLM wrapper (stream + sync)
├── speech_service.py     # TTS synthesis + STT recognition
├── data_filter.py        # Role-based order field filtering
├── order_service.py      # Order fetching & context resolution
├── order_cache.py        # File-based JSON order caching
├── user_service.py       # Email verification & user lookup
├── state_service.py      # State info Q&A loop
├── permit_service.py     # Permit info Q&A loop
├── conversation.py       # Conversation history management
├── location_weather.py   # Geolocation & weather API
└── proactive_monitor.py  # Background monitoring + alert generation
pipelines/        # Data processing pipelines
├── preprocessing.py      # Order data transformation
├── etl_orders.py         # API → MongoDB ingestion
├── rag_provisions.py     # FAISS/LangChain RAG for provisions
└── query_processor.py    # LLM-driven key extraction & filters
assistant/        # Application layer
├── __init__.py           # Brain orchestrator (generate_response, handle_query)
└── voice_app.py          # Voice app entry point & main loop
```

---

## Quick Start

### Prerequisites

- Python 3.10+
- MongoDB Atlas cluster (or local MongoDB)
- [Groq API key](https://console.groq.com/)

### Installation

```bash
# Clone the repository
git clone https://github.com/karrrtik-2/heavyhaul-ai-logistics.git
cd HeavyHaul_AI

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -e .

# For development tools
pip install -e ".[dev]"
```

### Configuration

```bash
# Copy the example env file and fill in your keys
cp .env.example .env
```

**Required** environment variables:
| Variable | Description |
|---|---|
| `MONGO_URI` | MongoDB connection string |
| `GROQ_API_KEY` | Groq API key for Llama 3.3 |

**Optional** (feature-specific):
| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | For RAG embeddings (text-embedding-ada-002) |
| `DEEP_INFRA_KEY` | Alternative LLM via DeepInfra |
| `GEMINI_KEY` | Google Gemini for OCR tasks |
| `WEATHER_API_KEY` | OpenWeatherMap API key |

**Optional** (proactive assistant):
| Variable | Description | Default |
|---|---|---|
| `PROACTIVE_ENABLED` | Enable/disable proactive monitoring | `true` |
| `PROACTIVE_POLL_INTERVAL` | Seconds between order/permit/deadline checks | `120` |
| `PROACTIVE_WEATHER_INTERVAL` | Seconds between route weather checks | `1800` |
| `PROACTIVE_PERMIT_WARNING_DAYS` | Warn when permit is within N days of expiry | `3` |
| `PROACTIVE_DEADLINE_WARNING_HOURS` | Warn when delivery is within N hours | `24` |
| `PROACTIVE_ALERT_CHECK_INTERVAL` | Seconds between alert delivery checks in voice loop | `15` |

### Running

```bash
# Start the voice assistant
python -m assistant.voice_app

# Or via the installed entry point
heavyhaul
```

### Docker

```bash
# Build image
docker build -t heavyhaul-ai .

# Run with environment variables
docker run --rm -it --env-file .env heavyhaul-ai
```

> Note: voice input/output from inside containers can be limited without host audio device mapping.

---

## How It Works

### Voice Interaction Flow

1. **Wake Word** → System listens for "James" or "Pixel"
2. **User Authentication** → Email verification against MongoDB
3. **Role Detection** → Assigns driver/client/admin permissions
4. **Intent Routing** → Detects orders, permits, or provisions context
5. **Query Processing** → LLM generates response from filtered data
6. **Speech Output** → Edge-TTS streams response audio

### Proactive Assistant Flow

When enabled, the voice app starts a `ProactiveMonitor` after login and runs checks in the background while normal conversations continue.

It proactively detects:

- **Order status changes** (e.g., dispatched → delivered)
- **New order assignments**
- **Permit issues** (expiring soon, expired, rejected, cancelled)
- **Delivery deadlines** (approaching or overdue)
- **Severe route weather** (storms, flood risk, high wind, etc.)

Alerts are prioritized (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`), deduplicated, and summarized via LLM into a short spoken update.

You can ask for updates explicitly with phrases like:

- "any updates"
- "any alerts"
- "what's new"
- "pending alerts"
- "catch me up"

### Intent Switching

The assistant routes queries between three subsystems:

- **Orders** — Natural language queries over order data (default)
- **Permits** — State-specific permit information Q&A
- **Provisions** — State provision document search via RAG

Switch between systems using natural phrases like *"switch to permits"* or *"talk about orders"*.

### Role-Based Filtering

Each role sees different data fields:

- **Driver** — Order details relevant to driving (no financial data, no metadata)
- **Client** — Order status and logistics (no internal metadata)  
- **Admin** — Full order data (financial, metadata included)

---

## Data Pipelines

### ETL Pipeline

Fetches orders from the external logistics API, preprocesses fields, and upserts into MongoDB:

```python
from pipelines.etl_orders import process_api_order

process_api_order("2883")
```

### RAG Pipeline

Processes state provision PDFs into queryable vector stores:

```python
from pipelines.rag_provisions import process_state_provisions

results = process_state_provisions("Arizona")
```

---

## Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov --cov-report=html
```

---

## Tech Stack

| Category | Technologies |
|---|---|
| **LLM** | Groq (Llama 3.3 70B), DeepInfra, OpenAI |
| **Speech** | edge-tts, SpeechRecognition, pygame |
| **Database** | MongoDB Atlas (pymongo) |
| **RAG** | LangChain, FAISS, ChromaDB, OpenAI Embeddings |
| **ETL** | pdfplumber, EasyOCR, PyPDF2, Google Gemini |
| **Config** | python-dotenv, dataclasses |

MIT


