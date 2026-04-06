"""Voice I/O for J.A.R.V.I.S. — Speech recognition, wake word detection, TTS, and personality fillers."""

import logging
import os
import platform
import random
import re
import subprocess
import tempfile
import time

import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav_io
import speech_recognition as sr

logger = logging.getLogger("jarvis.voice")

try:
    import pyaudio  # noqa: F401
    _HAS_PYAUDIO = True
except ImportError:
    _HAS_PYAUDIO = False


MIN_ENERGY_THRESHOLD = 50


class JarvisVoice:
    def __init__(self, config):
        self.config = config
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = config.get(
            "speech_recognition", "energy_threshold", default=150
        )
        self.recognizer.pause_threshold = config.get(
            "speech_recognition", "pause_threshold", default=1.0
        )
        self.recognizer.dynamic_energy_threshold = True

        self._tts_engine = config.get("voice", "engine", default="macos")
        self._pyttsx3 = None

        if self._tts_engine != "macos" or platform.system() != "Darwin":
            self._init_pyttsx3()

    def _init_pyttsx3(self):
        try:
            import pyttsx3
            self._pyttsx3 = pyttsx3.init()
            voices = self._pyttsx3.getProperty("voices")
            for voice in voices:
                if "english" in voice.name.lower():
                    self._pyttsx3.setProperty("voice", voice.id)
                    break
            self._pyttsx3.setProperty(
                "rate", self.config.get("voice", "rate", default=180)
            )
            self._tts_engine = "pyttsx3"
        except Exception as e:
            logger.warning(f"pyttsx3 init failed, using macOS say: {e}")
            self._tts_engine = "macos"

    # ── Personality Fillers ──────────────────────────────────────

    def acknowledge(self):
        """Say a short filler before an expensive operation."""
        from jarvis.brain import ACKNOWLEDGEMENTS
        self.speak(random.choice(ACKNOWLEDGEMENTS))

    def maybe_follow_up(self):
        """Optionally offer a follow-up after responding (default: off)."""
        prob = float(
            self.config.get("behavior", "follow_up_probability", default=0.0)
        )
        if prob <= 0 or random.random() > prob:
            return
        from jarvis.brain import FOLLOW_UPS
        time.sleep(0.5)
        self.speak(random.choice(FOLLOW_UPS))

    # ── Text-to-Speech ──────────────────────────────────────────

    def speak(self, text):
        logger.info(f"JARVIS: {text}")
        print(f"\n  \033[96m⟫ JARVIS:\033[0m {text}")

        try:
            if self._tts_engine == "macos" and platform.system() == "Darwin":
                voice = self.config.get("voice", "macos_voice", default="Daniel")
                subprocess.run(
                    ["say", "-v", voice, "-r", "190", text],
                    check=True,
                    capture_output=True,
                )
            elif self._pyttsx3:
                self._pyttsx3.say(text)
                self._pyttsx3.runAndWait()
            else:
                self._init_pyttsx3()
                if self._pyttsx3:
                    self._pyttsx3.say(text)
                    self._pyttsx3.runAndWait()
        except Exception as e:
            logger.error(f"TTS error: {e}")

    # ── Speech Recognition (OpenAI Whisper) ─────────────────────

    def _transcribe_whisper(self, audio_path, prompt=None):
        """Transcribe audio using OpenAI Whisper API for high-accuracy recognition.

        Optional *prompt* nudges the model (use for short wake phrases).
        """
        try:
            api_key = self.config.get("api_keys", "openai", default="")
            if not api_key:
                return self._transcribe_google(audio_path)

            import urllib.request
            import json
            import uuid

            boundary = uuid.uuid4().hex
            with open(audio_path, "rb") as f:
                audio_data = f.read()

            parts_tail = (
                f"\r\n--{boundary}\r\n"
                f'Content-Disposition: form-data; name="model"\r\n\r\n'
                f"whisper-1"
                f"\r\n--{boundary}\r\n"
                f'Content-Disposition: form-data; name="language"\r\n\r\n'
                f"en"
            )
            if prompt:
                parts_tail += (
                    f"\r\n--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="prompt"\r\n\r\n'
                    f"{prompt}"
                )
            parts_tail += f"\r\n--{boundary}--\r\n"

            body = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="audio.wav"\r\n'
                f"Content-Type: audio/wav\r\n\r\n"
            ).encode() + audio_data + parts_tail.encode()

            req = urllib.request.Request(
                "https://api.openai.com/v1/audio/transcriptions",
                data=body,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                },
            )

            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode())

            text = result.get("text", "").strip()
            if text:
                logger.info(f"Whisper heard: {text}")
                return text
            return None

        except Exception as e:
            logger.warning(f"Whisper API error, falling back to Google: {e}")
            return self._transcribe_google(audio_path)

    @staticmethod
    def _standby_transcript_is_actionable(text):
        """True if transcript might be the user (not obvious TV/noise spam)."""
        if not text:
            return False
        t = text.lower().strip()
        if len(t) < 2:
            return False
        junk = {
            ".", "..", "...", "you", "hm", "hmm", "uh", "um", "yeah", "oh",
        }
        if t in junk:
            return False
        hints = (
            "wake", "dog", "home", "brodie", "bigbrodie", "jarvis",
            "hey", "hello", "hi,", "hi ", "yes",
            "open", "close", "play", "what", "time", "weather", "read",
            "send", "alarm", "spotify", "mail", "email", "news",
        )
        return any(h in t for h in hints)

    def _wake_phrase_fuzzy_match(self, text, wake_phrase):
        """True if every significant token of *wake_phrase* appears in *text* (Whisper-tolerant)."""
        if not text or not wake_phrase:
            return False
        compact = re.sub(r"[^a-z0-9]", "", text.lower())
        parts = []
        for raw in wake_phrase.lower().split():
            w = raw.strip(".,!?\"")
            if w.endswith("'s"):
                w = w[:-2]
            elif w.endswith("'"):
                w = w[:-1]
            w = "".join(c for c in w if c.isalnum())
            if not w:
                continue
            if len(w) < 2 and w != "up":
                continue
            parts.append(w)
        if not parts:
            return False
        return all(p in compact for p in parts)

    def _wake_passes_jarvis_gate(self, text):
        """If enabled, only wake when transcript contains *Jarvis* (or common mis-hears)."""
        if not self.config.get(
            "behavior", "wake_requires_jarvis_keyword", default=True
        ):
            return True
        t = (text or "").lower()
        if "jarvis" in t:
            return True
        for a in self.config.get("behavior", "wake_jarvis_aliases", default=[]):
            if isinstance(a, str) and a.strip() and a.strip().lower() in t:
                logger.info(f"Wake gate: alias match '{a.strip().lower()}'")
                return True
        return False

    def _transcribe_google(self, audio_path):
        """Fallback: transcribe using Google's free speech API."""
        try:
            r = sr.Recognizer()
            with sr.AudioFile(audio_path) as source:
                audio = r.record(source)
            return r.recognize_google(audio, language="en-US")
        except (sr.UnknownValueError, sr.RequestError):
            return None

    def _record_audio(self, timeout=8, phrase_time_limit=15):
        """Record audio from mic, return path to WAV file or None."""
        if _HAS_PYAUDIO:
            return self._record_pyaudio(timeout, phrase_time_limit)
        return self._record_sounddevice(timeout, phrase_time_limit)

    def _record_pyaudio(self, timeout, phrase_time_limit, for_wake=False):
        try:
            with sr.Microphone() as source:
                if for_wake:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.7)
                    self.recognizer.energy_threshold = max(
                        MIN_ENERGY_THRESHOLD,
                        int(self.recognizer.energy_threshold),
                    )
                audio = self.recognizer.listen(
                    source, timeout=timeout, phrase_time_limit=phrase_time_limit
                )
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.write(audio.get_wav_data())
            tmp.close()
            return tmp.name
        except sr.WaitTimeoutError:
            return None
        except Exception as e:
            logger.error(f"Record error: {e}")
            return None

    def _record_sounddevice(self, timeout, phrase_time_limit):
        fs = 16000
        block_duration = 0.1
        block_size = int(fs * block_duration)
        silence_threshold = max(0.01, self.recognizer.energy_threshold / 32767.0)
        max_silent_blocks = int(1.5 / block_duration)

        frames = []
        silent_blocks = 0
        speaking = False
        start = time.time()

        def callback(indata, frame_count, time_info, status):
            nonlocal silent_blocks, speaking
            energy = np.sqrt(np.mean(indata ** 2))
            if energy > silence_threshold:
                if not speaking:
                    speaking = True
                silent_blocks = 0
                frames.append(indata.copy())
            elif speaking:
                silent_blocks += 1
                frames.append(indata.copy())

        try:
            with sd.InputStream(
                samplerate=fs, channels=1, blocksize=block_size, callback=callback
            ):
                while time.time() - start < (timeout + phrase_time_limit):
                    time.sleep(0.05)
                    if speaking and silent_blocks >= max_silent_blocks:
                        break
                    if time.time() - start > timeout and not speaking:
                        return None
        except Exception as e:
            logger.error(f"Sounddevice error: {e}")
            return None

        if not speaking or not frames:
            return None

        audio_data = np.concatenate(frames)
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        wav_io.write(tmp.name, fs, (audio_data * 32767).astype(np.int16))
        tmp.close()
        return tmp.name

    def listen(self, timeout=8, phrase_time_limit=None):
        """Listen for speech and return recognized text using Whisper API."""
        if phrase_time_limit is None:
            phrase_time_limit = self.config.get(
                "speech_recognition", "phrase_time_limit", default=15
            )

        audio_path = self._record_audio(timeout, phrase_time_limit)
        if not audio_path:
            return None

        try:
            text = self._transcribe_whisper(audio_path)
            if text:
                print(f"  \033[93m⟫ You:\033[0m {text}")
                return text.strip()
            return None
        finally:
            try:
                os.unlink(audio_path)
            except OSError:
                pass

    # ── Wake Word Detection ─────────────────────────────────────

    def listen_for_wake_word(self):
        """Block until a wake word is detected. Returns True when heard."""
        wake_words = self.config.get(
            "wake_words", default=["wake up", "hey jarvis", "jarvis"]
        )
        wake_limit = self.config.get(
            "speech_recognition", "wake_phrase_limit", default=3
        )

        if _HAS_PYAUDIO:
            return self._wake_pyaudio(wake_words, wake_limit)
        return self._wake_sounddevice(wake_words, wake_limit)

    def _wake_pyaudio(self, wake_words, phrase_limit):
        try:
            wake_timeout = self.config.get(
                "speech_recognition", "wake_listen_timeout", default=12
            )
            audio_path = self._record_pyaudio(
                timeout=wake_timeout,
                phrase_time_limit=phrase_limit,
                for_wake=True,
            )
            if not audio_path:
                return False

            wp = " ".join(wake_words) if wake_words else "Jarvis"
            wake_prompt = f"{wp}. Hey Jarvis. Yes Jarvis."
            text = self._transcribe_whisper(audio_path, prompt=wake_prompt)
            try:
                os.unlink(audio_path)
            except OSError:
                pass

            if not text:
                return False

            text = text.lower().strip().rstrip(".")
            logger.info(f"Wake check heard: '{text}'")
            if self._standby_transcript_is_actionable(text):
                print(f"\r  \033[2m⟫ Heard: \"{text}\"\033[0m" + " " * 20)

            for w in wake_words:
                if w in text:
                    if self._wake_passes_jarvis_gate(text):
                        return True
                    logger.info("Wake rejected: need 'jarvis' in transcript")
                    return False

            if (
                len(wake_words) == 1
                and wake_words[0].lower().strip() == "jarvis"
                and self._wake_passes_jarvis_gate(text)
            ):
                logger.info("Wake: Jarvis keyword or alias (e.g. jervis)")
                return True

            for phrase in wake_words:
                if self._wake_phrase_fuzzy_match(text, phrase):
                    logger.info(f"Fuzzy wake match (tokens): '{phrase}' ~ '{text}'")
                    if self._wake_passes_jarvis_gate(text):
                        return True
                    logger.info("Wake rejected: need 'jarvis' in transcript")
                    return False

            # Legacy mis-hears for "wake up dog"
            legacy = [
                "wake up doug", "wake up doc", "wake up dawg", "wake a dog",
                "wake up dug", "wake up dark", "wake of dog", "wakeup dog",
            ]
            for trigger in legacy:
                if trigger in text:
                    logger.info(f"Fuzzy wake match: '{trigger}' in '{text}'")
                    if self._wake_passes_jarvis_gate(text):
                        return True
                    return False

            return False
        except Exception as e:
            logger.error(f"Wake word error: {e}")
            time.sleep(1)
            return False

    def _wake_sounddevice(self, wake_words, phrase_limit):
        text = self._listen_sounddevice(timeout=30, phrase_time_limit=phrase_limit)
        if not text:
            return False
        t = text.lower()
        if not self._wake_passes_jarvis_gate(t):
            return False
        if len(wake_words) == 1 and wake_words[0].lower().strip() == "jarvis":
            return True
        return any(w in t for w in wake_words)

    # ── Clap Detection ──────────────────────────────────────────

    def listen_for_clap(self):
        """Detect a double-clap pattern (two sharp spikes within ~0.7s).

        Uses sounddevice to monitor audio in real-time. A clap is a sudden
        energy spike well above ambient noise that decays quickly. Two claps
        within 0.3-0.8 seconds triggers activation — like Tony Stark.
        """
        fs = 16000
        block_ms = 30
        block_size = int(fs * block_ms / 1000)

        clap_cfg = self.config.get("clap", default={})
        spike_multiplier = clap_cfg.get("spike_multiplier", 8.0)
        min_gap = clap_cfg.get("min_gap", 0.15)
        max_gap = clap_cfg.get("max_gap", 0.8)

        ambient_levels = []
        clap_times = []
        detected = False
        start = time.time()
        max_listen = 10.0

        def callback(indata, frame_count, time_info, status):
            nonlocal detected
            if detected:
                return

            energy = np.sqrt(np.mean(indata ** 2))
            now = time.time()

            ambient_levels.append(energy)
            if len(ambient_levels) > 100:
                ambient_levels.pop(0)

            ambient = np.median(ambient_levels) if len(ambient_levels) > 10 else 0.005
            threshold = max(0.02, ambient * spike_multiplier)

            if energy > threshold:
                if not clap_times or (now - clap_times[-1]) > min_gap:
                    clap_times.append(now)
                    logger.debug(f"Clap spike: energy={energy:.4f} threshold={threshold:.4f}")

                    if len(clap_times) >= 2:
                        gap = clap_times[-1] - clap_times[-2]
                        if min_gap <= gap <= max_gap:
                            detected = True

            while clap_times and (now - clap_times[0]) > max_gap + 0.5:
                clap_times.pop(0)

        try:
            with sd.InputStream(
                samplerate=fs, channels=1, blocksize=block_size, callback=callback
            ):
                while not detected and (time.time() - start) < max_listen:
                    time.sleep(0.02)
        except Exception as e:
            logger.error(f"Clap detection error: {e}")
            return False

        if detected:
            logger.info("Double-clap detected!")
            print(f"\r  \033[92m⟫ *clap clap* detected\033[0m" + " " * 20)
        return detected

    def wait_for_wake(self):
        """Wait for either a clap or a wake word, depending on config."""
        method = self.config.get("wake_method", default="both")

        if method == "clap":
            return self.listen_for_clap()
        elif method == "voice":
            return self.listen_for_wake_word()
        else:
            return self._wait_for_either()

    def _wait_for_either(self):
        """Single audio stream that detects both claps AND speech.

        Monitors mic continuously. Sharp energy spikes are checked for
        double-clap pattern. Sustained sound above threshold is recorded
        and sent to Google for wake-word recognition. Nothing gets missed.
        """
        fs = 16000
        block_ms = 30
        block_size = int(fs * block_ms / 1000)

        clap_cfg = self.config.get("clap", default={})
        spike_multiplier = clap_cfg.get("spike_multiplier", 8.0)
        min_gap = clap_cfg.get("min_gap", 0.15)
        max_gap = clap_cfg.get("max_gap", 0.8)
        wake_words = self.config.get(
            "wake_words", default=["wake up", "hey jarvis", "jarvis"]
        )

        ambient_levels = []
        clap_times = []
        speech_frames = []
        speech_start = None
        speech_threshold = max(0.01, self.recognizer.energy_threshold / 32767.0)
        silent_blocks = 0
        max_silent = int(1.2 / (block_ms / 1000))
        max_speech = float(
            self.config.get("speech_recognition", "wake_max_speech_seconds", default=8.0)
        )

        result = {"type": None}

        def callback(indata, frame_count, time_info, status):
            nonlocal speech_start, silent_blocks
            if result["type"]:
                return

            energy = np.sqrt(np.mean(indata ** 2))
            now = time.time()

            ambient_levels.append(energy)
            if len(ambient_levels) > 150:
                ambient_levels.pop(0)
            ambient = np.median(ambient_levels) if len(ambient_levels) > 20 else 0.005
            clap_threshold = max(0.02, ambient * spike_multiplier)

            if energy > clap_threshold:
                if not clap_times or (now - clap_times[-1]) > min_gap:
                    clap_times.append(now)
                    if len(clap_times) >= 2:
                        gap = clap_times[-1] - clap_times[-2]
                        if min_gap <= gap <= max_gap:
                            result["type"] = "clap"
                            return

            while clap_times and (now - clap_times[0]) > max_gap + 0.5:
                clap_times.pop(0)

            if energy > speech_threshold:
                if speech_start is None:
                    speech_start = now
                silent_blocks = 0
                speech_frames.append(indata.copy())
            elif speech_start is not None:
                silent_blocks += 1
                speech_frames.append(indata.copy())
                if silent_blocks >= max_silent:
                    duration = now - speech_start
                    if duration >= 0.4:
                        result["type"] = "speech"
                    else:
                        speech_frames.clear()
                        speech_start = None
                        silent_blocks = 0

            if speech_start and (now - speech_start) > max_speech:
                result["type"] = "speech"

        try:
            with sd.InputStream(
                samplerate=fs, channels=1, blocksize=block_size, callback=callback
            ):
                while not result["type"]:
                    time.sleep(0.02)
        except Exception as e:
            logger.error(f"Wake listener error: {e}")
            return False

        if result["type"] == "clap":
            logger.info("Double-clap detected!")
            print(f"\r  \033[92m⟫ *clap clap* detected\033[0m" + " " * 20)
            return True

        if result["type"] == "speech" and speech_frames:
            audio_data = np.concatenate(speech_frames)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name
                wav_io.write(tmp_path, fs, (audio_data * 32767).astype(np.int16))
            try:
                wp = " ".join(wake_words) if wake_words else "Jarvis"
                wake_prompt = f"{wp}. Hey Jarvis. Yes Jarvis."
                text = self._transcribe_whisper(tmp_path, prompt=wake_prompt)
                if text:
                    text = text.lower().strip().rstrip(".")
                    logger.info(f"Wake check heard: '{text}'")
                    if self._standby_transcript_is_actionable(text):
                        print(f"\r  \033[2m⟫ Heard: \"{text}\"\033[0m" + " " * 20)
                    if any(w in text for w in wake_words):
                        if self._wake_passes_jarvis_gate(text):
                            logger.info("Wake word detected!")
                            return True
                    if (
                        len(wake_words) == 1
                        and wake_words[0].lower().strip() == "jarvis"
                        and self._wake_passes_jarvis_gate(text)
                    ):
                        logger.info("Wake word detected (Jarvis / alias)!")
                        return True
                    for phrase in wake_words:
                        if self._wake_phrase_fuzzy_match(text, phrase):
                            if self._wake_passes_jarvis_gate(text):
                                logger.info("Wake word detected (fuzzy tokens)!")
                                return True
                    for trigger in ("wake up dog", "wake up doug", "wakeup dog"):
                        if trigger in text and self._wake_passes_jarvis_gate(text):
                            logger.info(f"Wake fuzzy: {trigger}")
                            return True
            except Exception:
                pass
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        return False

    # ── Calibration ─────────────────────────────────────────────

    def calibrate(self):
        print("  \033[2m⟫ Calibrating microphone...\033[0m")
        try:
            if _HAS_PYAUDIO:
                with sr.Microphone() as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=2)
            else:
                silence = sd.rec(int(2 * 16000), samplerate=16000, channels=1)
                sd.wait()
                noise_level = np.sqrt(np.mean(silence ** 2))
                self.recognizer.energy_threshold = noise_level * 32767 * 1.5

            self.recognizer.energy_threshold = max(
                MIN_ENERGY_THRESHOLD,
                self.recognizer.energy_threshold,
            )

            print(
                f"  \033[2m⟫ Energy threshold: "
                f"{self.recognizer.energy_threshold:.0f}\033[0m"
            )
        except Exception as e:
            logger.warning(f"Calibration error: {e}")
            self.recognizer.energy_threshold = MIN_ENERGY_THRESHOLD
            print("  \033[2m⟫ Using default microphone settings\033[0m")
