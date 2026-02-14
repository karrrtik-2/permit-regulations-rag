# Setup Guide

## System Requirements

- **Python** 3.10 or higher
- **MongoDB** Atlas cluster (free tier works) or local MongoDB 6.0+
- **Microphone** for voice input (optional — can use text mode)
- **Speakers** for TTS audio output

### Optional System Dependencies

| Feature | Dependency |
|---|---|
| OCR (permit PDF extraction) | [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) |
| OCR (advanced) | Google Gemini API key |
| RAG provisions | OpenAI API key (for embeddings) |
| Streamlit demo | `pip install -e ".[demo]"` |

---

## Installation

### 1. Clone and Set Up Environment

```bash
git clone https://github.com/karrrtik-2/heavyhaul-ai-logistics.git
cd heavyhaul-ai-logistics

python -m venv .venv

# Activate
.venv\Scripts\activate        # Windows (PowerShell)
.venv\Scripts\activate.bat    # Windows (CMD)
source .venv/bin/activate     # macOS / Linux

pip install -e .
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your API keys:

```dotenv
MONGO_URI=mongodb+srv://user:password@cluster.mongodb.net/?retryWrites=true&w=majority
GROQ_API_KEY=gsk_xxxxxxxxxxxxx
```

### 3. Verify MongoDB Collections

The application expects these collections in the `HeavyHaulDB` database:

| Collection | Purpose |
|---|---|
| `All Orders` | Order documents |
| `Drivers` | Driver profiles with order associations |
| `Clients` | Client profiles with order associations |
| `Companies` | Company profiles |
| `All States` | State information and provision data |
| `All Users` | User accounts for authentication |

### 4. Run

```bash
# Voice assistant
python -m assistant.voice_app

# Or via entry point (after pip install)
heavyhaul
```

---

## Development Setup

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check .

# Run type checker
mypy .
```

---

## Troubleshooting

### "MONGO_URI environment variable is required"

Ensure your `.env` file exists in the project root and contains a valid `MONGO_URI`.

### Speech recognition not working

- Check microphone permissions in your OS settings
- Ensure `SpeechRecognition` and `PyAudio` are installed
- On Windows, `PyAudio` may require: `pip install pipwin && pipwin install pyaudio`

### TTS audio not playing

- Ensure `pygame` is installed and your audio output device is working
- Check that the `assets/stream_audios/` directory exists (created automatically)

### Tesseract not found (OCR features)

Set the `TESSERACT_CMD` environment variable to your Tesseract installation path:

```dotenv
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```


