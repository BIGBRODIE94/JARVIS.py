"""Configuration management for J.A.R.V.I.S."""

import json
import os
from pathlib import Path

JARVIS_DIR = Path.home() / ".jarvis"
CONFIG_FILE = JARVIS_DIR / "config.json"
HISTORY_FILE = JARVIS_DIR / "history.json"
LOG_FILE = JARVIS_DIR / "jarvis.log"
PID_FILE = JARVIS_DIR / "jarvis.pid"

DEFAULT_CONFIG = {
    "user_name": "BigBrodie",
    "wake_words": ["wake up", "hey jarvis", "jarvis"],
    "ai_provider": "openai",
    "ai_model": "gpt-4o-mini",
    "api_keys": {
        "openai": "",
        "gemini": "",
        "groq": ""
    },
    "ollama_model": "llama3.2",
    "ollama_url": "http://localhost:11434",
    "voice": {
        "engine": "macos",
        "macos_voice": "Daniel",
        "rate": 180,
        "volume": 1.0
    },
    "speech_recognition": {
        "energy_threshold": 300,
        "pause_threshold": 0.8,
        "phrase_time_limit": 15,
        "wake_phrase_limit": 3
    },
    "wake_method": "both",
    "clap": {
        "spike_multiplier": 8.0,
        "min_gap": 0.15,
        "max_gap": 0.8
    },
    "behavior": {
        "greet_on_wake": True,
        "announce_time": True,
        "sleep_after_idle": 180
    }
}


class JarvisConfig:
    def __init__(self):
        self._ensure_dirs()
        self.config = self._load()

    def _ensure_dirs(self):
        JARVIS_DIR.mkdir(parents=True, exist_ok=True)

    def _load(self):
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE) as f:
                saved = json.load(f)
            merged = DEFAULT_CONFIG.copy()
            self._deep_merge(merged, saved)
            return merged
        return DEFAULT_CONFIG.copy()

    def _deep_merge(self, base, override):
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def save(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=2)

    def get(self, *keys, default=None):
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    def set(self, *keys_and_value):
        keys = keys_and_value[:-1]
        value = keys_and_value[-1]
        d = self.config
        for key in keys[:-1]:
            d = d.setdefault(key, {})
        d[keys[-1]] = value
        self.save()

    @property
    def is_configured(self):
        provider = self.get("ai_provider")
        if provider == "ollama":
            return True
        api_key = self.get("api_keys", provider)
        return bool(api_key)

    def setup_wizard(self):
        """Interactive first-time setup."""
        print("\n" + "=" * 60)
        print("  J.A.R.V.I.S. — First Time Setup")
        print("=" * 60)

        name = input(
            f"\n  What should I call you? [{self.get('user_name')}]: "
        ).strip()
        if name:
            self.set("user_name", name)

        print("\n  Choose your AI provider:")
        print("    1. OpenAI  (GPT-4o, GPT-4o-mini) — Best quality, needs API key")
        print("    2. Google Gemini              — Free tier available")
        print("    3. Groq    (Llama, Mixtral)   — Free tier, very fast")
        print("    4. Ollama  (Local models)     — Free, private, no internet")

        choice = input("\n  Select provider [1-4]: ").strip()
        providers = {"1": "openai", "2": "gemini", "3": "groq", "4": "ollama"}
        provider = providers.get(choice, "openai")
        self.set("ai_provider", provider)

        if provider == "ollama":
            model = input(
                f"  Ollama model [{self.get('ollama_model')}]: "
            ).strip()
            if model:
                self.set("ollama_model", model)
        else:
            key_prompts = {
                "openai": "  OpenAI API key (platform.openai.com/api-keys): ",
                "gemini": "  Gemini API key (aistudio.google.com/apikey): ",
                "groq": "  Groq API key (console.groq.com/keys): ",
            }
            key = input(key_prompts[provider]).strip()
            if key:
                self.set("api_keys", provider, key)

            default_models = {
                "openai": "gpt-4o-mini",
                "gemini": "gemini-2.0-flash",
                "groq": "llama-3.3-70b-versatile",
            }
            model = input(
                f"  AI model [{default_models[provider]}]: "
            ).strip()
            self.set("ai_model", model or default_models[provider])

        print("\n  Voice settings (macOS):")
        print("    Recommended voices: Daniel (British), Samantha, Alex")
        voice = input("  Voice name [Daniel]: ").strip()
        if voice:
            self.set("voice", "macos_voice", voice)

        self.save()
        print(f"\n  ✓ Configuration saved to {CONFIG_FILE}")
        print("  ✓ You can edit this file anytime to change settings.\n")
