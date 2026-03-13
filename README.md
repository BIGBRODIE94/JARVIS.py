# J.A.R.V.I.S. — Just A Rather Very Intelligent System

An AI-powered personal assistant inspired by Tony Stark's JARVIS from Iron Man. Features real AI conversation (GPT-4o, Gemini, Groq, Ollama), voice interaction, double-clap activation, and an always-on background service.

## Features

- **AI Conversation** — Talk naturally like ChatGPT, powered by OpenAI, Google Gemini, Groq, or local Ollama
- **JARVIS Personality** — British wit, dry humor, formal tone. Never breaks character.
- **Double-Clap Activation** — Clap twice like Tony Stark to wake JARVIS
- **Voice Wake Word** — Say "Wake Up" or "Hey Jarvis"
- **Always-On Background Service** — Starts on login via macOS LaunchAgent
- **System Commands** — Open apps, websites, play music, screenshots, volume, lock screen
- **Weather, Time, System Diagnostics** — Real-time info on demand
- **Ambient Status Reports** — Hourly updates on battery, CPU, disk
- **LLM Intent Parsing** — Natural language command routing, no rigid keywords needed

## Quick Start

```bash
git clone https://github.com/BIGBRODIE94/JARVIS.py.git
cd JARVIS.py
./setup_jarvis.sh
```

The setup script handles everything: creates a venv, installs dependencies, configures your AI provider, and installs the always-on background service.

## Usage

### Background Mode (always-on, recommended)
```bash
./setup_jarvis.sh    # One-time setup — JARVIS runs forever after this
```

### Interactive Mode
```bash
source venv/bin/activate   # If venv is in this directory
python3 Jarvis.py          # Full voice mode
python3 Jarvis.py --text   # Text-only mode
python3 Jarvis.py --setup  # Re-configure AI provider / API key
```

## Wake Methods

| Method | How | Config |
|--------|-----|--------|
| Double-clap | Clap twice quickly | `"wake_method": "clap"` |
| Voice | Say "Wake Up" / "Hey Jarvis" | `"wake_method": "voice"` |
| Both | Either works | `"wake_method": "both"` (default) |

## AI Providers

| Provider | Cost | Setup |
|----------|------|-------|
| OpenAI (GPT-4o) | Paid | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| Google Gemini | Free tier | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| Groq | Free tier | [console.groq.com/keys](https://console.groq.com/keys) |
| Ollama (local) | Free | [ollama.com](https://ollama.com) |

## Project Structure

```
├── Jarvis.py              # Main entry point
├── jarvis/
│   ├── __init__.py
│   ├── brain.py           # AI engine, personality, intent parsing, tool calling
│   ├── commands.py        # System commands (40+ apps, weather, lock, screenshot, etc.)
│   ├── config.py          # Configuration management (~/.jarvis/config.json)
│   └── voice.py           # Speech I/O, wake word, clap detection, TTS
├── requirements.txt
└── setup_jarvis.sh        # One-click installer + LaunchAgent setup
```

## Configuration

All settings live in `~/.jarvis/config.json`. Key options:

- `user_name` — What JARVIS calls you
- `ai_provider` — openai / gemini / groq / ollama
- `wake_method` — clap / voice / both
- `voice.macos_voice` — macOS TTS voice (Daniel = British JARVIS)
- `behavior.sleep_after_idle` — Seconds before auto-standby

## Requirements

- Python 3.10+
- macOS (primary), Linux/Windows (partial support)
- Microphone access
- Internet connection (for AI + speech recognition)
