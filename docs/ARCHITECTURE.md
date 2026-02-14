# Architecture

## Overview

HeavyHaul AI is a voice-driven logistics assistant built on a **layered architecture** with clear separation of concerns:

```
┌─────────────────────────────────────────┐
│           Assistant Layer                │  Entry point, orchestration
│  (voice_app.py, __init__.py)            │
├─────────────────────────────────────────┤
│           Proactive Layer                │  Background monitoring, alerts
│  (proactive_monitor.py)                 │
├─────────────────────────────────────────┤
│           Services Layer                 │  Business logic, LLM, speech
│  (llm_client, speech, filters, etc.)    │
├─────────────────────────────────────────┤
│           Pipelines Layer                │  ETL, RAG, query processing
│  (etl_orders, rag_provisions, etc.)     │
├─────────────────────────────────────────┤
│           Data Layer                     │  MongoDB, file cache, vectors
│  (db/, order_cache, chroma_db)          │
├─────────────────────────────────────────┤
│           Config Layer                   │  Settings, constants, env
│  (settings.py, constants.py, .env)      │
└─────────────────────────────────────────┘
```

## Design Decisions

### Singleton Database Connection

`db/__init__.py` provides a singleton `MongoDatabase` class. All modules access the database through `get_db()` — no module creates its own connection.

### Dataclass-Based Configuration

All settings are defined as frozen dataclasses in `config/settings.py`, loaded from environment variables at import time. This gives:
- Type safety and IDE autocompletion
- Immutability (prevents accidental mutation)
- Single source of truth for all configuration
- Easy validation via `settings.validate()`

### Role-Based Data Filtering

The `data_filter.py` service implements recursive field exclusion to produce role-appropriate views of order data. Rather than fetching different queries per role, we fetch once and filter — simpler and more maintainable.

### Intent Routing

The assistant uses keyword matching (via frozen sets in `constants.py`) to route between three subsystems (orders, permits, provisions). This is fast, deterministic, and doesn't require an extra LLM call.

### LLM-Driven Key Extraction

For order queries, the system asks the LLM to identify relevant schema keys from the user's natural language question, then fetches only those fields. This is more flexible than hardcoded intent parsing.

### Proactive Monitoring

The `ProactiveMonitor` runs background asyncio tasks that periodically poll MongoDB for changes. Rather than relying on database triggers (which would require MongoDB change streams), we use a polling approach with deduplication:
- **Order status polling** (every 2 min default) — snapshots previous statuses and diffs
- **Weather monitoring** (every 30 min) — checks OpenWeatherMap for severe conditions along active routes
- **Permit expiration tracking** — estimates expiry from attach dates and warns ahead of time
- **Deadline reminders** — scans date fields and alerts when hours remaining drops below threshold
- **New order detection** — diffs order ID sets between cycles

Alerts are prioritized (CRITICAL > HIGH > MEDIUM > LOW), deduplicated by a composite key, and summarized via LLM into natural speech before delivery.

## Data Flow

### Voice Query Flow

```
User Speech
    → SpeechRecognition (STT)
    → handle_query() routing
    → generate_response() / state_service / permit_service
    → Groq LLM (streaming)
    → split_sentences()
    → edge-tts (TTS)
    → pygame audio playback
```

### Proactive Alert Flow

```
Background Monitor (asyncio tasks)
    → Poll MongoDB for changes
    → Detect: status changes / permit expiry / weather / deadlines / new orders
    → Generate ProactiveAlert objects (prioritized, deduplicated)
    → Queue pending alerts
    → Main loop checks between voice interactions
    → LLM summarizes alerts into natural speech
    → edge-tts (TTS) → pygame audio playback
```

### ETL Flow

```
External API
    → fetch order JSON
    → preprocess_order_data()
    → MongoDB upsert (orders, drivers, clients, companies)
    → PDF permit extraction (optional)
```

### RAG Flow

```
State provision PDF (from MongoDB URL)
    → PyPDF2 text extraction
    → RecursiveCharacterTextSplitter
    → OpenAI embeddings → FAISS vector store
    → ConversationalRetrievalChain
    → DeepInfra LLM response
    → MongoDB update
```

## Module Dependencies

```
assistant/
  ├── services/llm_client
  ├── services/speech_service
  ├── services/data_filter
  ├── services/order_service
  ├── services/order_cache
  ├── services/user_service
  ├── services/state_service
  ├── services/permit_service
  ├── services/conversation
  ├── services/location_weather
  ├── services/proactive_monitor
  └── config/settings, config/constants

services/proactive_monitor
  ├── db/
  ├── services/llm_client
  ├── services/location_weather
  └── config/settings

pipelines/
  ├── db/
  ├── config/settings
  └── services/llm_client (query_processor only)

services/
  ├── db/
  ├── config/settings
  └── config/constants
```

No circular dependencies. All arrows point downward.
