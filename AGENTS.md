# AGENTS.md

## Cursor Cloud specific instructions

### Overview

This is **JARVIS.py** — a single-file Python voice assistant. It uses `pyttsx3` (text-to-speech), `SpeechRecognition` (Google Speech API via microphone), `wikipedia`, `pyautogui`, `psutil`, and `pyjokes`.

### Dependencies

- **System packages**: `espeak`, `espeak-ng`, `portaudio19-dev`, `python3-pyaudio`, `python3-tk`, `python3-dev`, `flac`, `alsa-utils`
- **Python packages**: listed in `requirements.txt`
- Use `pyttsx3==2.98` (not 2.99) — version 2.99 has a bug with espeak on Ubuntu (`SetVoiceByName failed` error).

### Running

- The main script `JARVIS.py` requires a **microphone and speakers** for its interactive loop. In a headless cloud VM, it cannot be run interactively.
- Use `demo_jarvis.py` to exercise core functions (TTS, time/date, jokes, CPU stats, Wikipedia) without microphone input. ALSA errors on stderr are expected (no sound card) and harmless.
- Voice index 7 is hardcoded in `JARVIS.py` — it maps to different voices depending on the espeak installation (e.g., "Belarusian" on cloud VMs vs. potentially a different voice on other systems).

### Linting

- No linter is configured in the repo. Use `python3 -m pyflakes JARVIS.py` for basic checks.
- `python3 -m py_compile JARVIS.py` for syntax validation.
- Pre-existing lint warnings: unused imports (`pyaudio`, `sys`) and undefined name (`songs` on line 172).

### Testing

- No test suite exists. Validate changes by running `demo_jarvis.py` and checking output.
