"""Voice I/O for J.A.R.V.I.S. — Speech recognition, wake word detection, TTS, and personality fillers."""

import logging
import os
import platform
import random
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


MIN_ENERGY_THRESHOLD = 300


class JarvisVoice:
    def __init__(self, config):
        self.config = config
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = max(
            MIN_ENERGY_THRESHOLD,
            config.get("speech_recognition", "energy_threshold", default=300),
        )
        self.recognizer.pause_threshold = config.get(
            "speech_recognition", "pause_threshold", default=0.8
        )
        self.recognizer.dynamic_energy_threshold = False

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
        """30% chance to offer a follow-up after responding."""
        if random.random() < 0.3:
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

    # ── Speech Recognition ──────────────────────────────────────

    def listen(self, timeout=8, phrase_time_limit=None):
        """Listen for speech and return recognized text, or None."""
        if phrase_time_limit is None:
            phrase_time_limit = self.config.get(
                "speech_recognition", "phrase_time_limit", default=15
            )

        if _HAS_PYAUDIO:
            return self._listen_pyaudio(timeout, phrase_time_limit)
        return self._listen_sounddevice(timeout, phrase_time_limit)

    def _listen_pyaudio(self, timeout, phrase_time_limit):
        try:
            with sr.Microphone() as source:
                audio = self.recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_time_limit,
                )
            text = self.recognizer.recognize_google(audio, language="en-US")
            logger.info(f"Heard: {text}")
            print(f"  \033[93m⟫ You:\033[0m {text}")
            return text.strip()
        except sr.WaitTimeoutError:
            return None
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            logger.error(f"Speech API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Listen error: {e}")
            return None

    def _listen_sounddevice(self, timeout, phrase_time_limit):
        """Fallback: record with sounddevice, then recognize."""
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

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
            wav_io.write(tmp_path, fs, (audio_data * 32767).astype(np.int16))

        try:
            r = sr.Recognizer()
            with sr.AudioFile(tmp_path) as source:
                audio = r.record(source)
            text = r.recognize_google(audio, language="en-US")
            logger.info(f"Heard: {text}")
            print(f"  \033[93m⟫ You:\033[0m {text}")
            return text.strip()
        except (sr.UnknownValueError, sr.RequestError):
            return None
        finally:
            os.unlink(tmp_path)

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
            with sr.Microphone() as source:
                audio = self.recognizer.listen(
                    source, timeout=None, phrase_time_limit=phrase_limit
                )
            print("\r  \033[2m⟫ Heard something, checking...\033[0m", end="", flush=True)
            text = self.recognizer.recognize_google(audio, language="en-US").lower()
            logger.info(f"Wake check heard: '{text}'")
            print(f"\r  \033[2m⟫ Heard: \"{text}\"\033[0m" + " " * 20)
            if any(w in text for w in wake_words):
                return True
            return False
        except sr.UnknownValueError:
            return False
        except sr.WaitTimeoutError:
            return False
        except sr.RequestError as e:
            logger.error(f"Wake word API error: {e}")
            print(f"\n  \033[91m⟫ Speech API error — check internet connection\033[0m")
            time.sleep(3)
            return False
        except Exception as e:
            logger.error(f"Wake word error: {e}")
            time.sleep(1)
            return False

    def _wake_sounddevice(self, wake_words, phrase_limit):
        text = self._listen_sounddevice(timeout=30, phrase_time_limit=phrase_limit)
        if text:
            return any(w in text.lower() for w in wake_words)
        return False

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
        """Listen for clap OR wake word simultaneously using threads."""
        import threading

        result = {"triggered": False, "source": None}
        stop_event = threading.Event()

        def clap_worker():
            while not stop_event.is_set() and not result["triggered"]:
                if self.listen_for_clap():
                    result["triggered"] = True
                    result["source"] = "clap"
                    stop_event.set()
                    return
                if stop_event.is_set():
                    return

        def voice_worker():
            while not stop_event.is_set() and not result["triggered"]:
                if self.listen_for_wake_word():
                    result["triggered"] = True
                    result["source"] = "voice"
                    stop_event.set()
                    return
                if stop_event.is_set():
                    return

        # Only one can use the mic at a time, so alternate between them.
        # Clap detection is fast (10s max) and doesn't need the internet.
        # Wake word needs the mic + Google API.
        # Strategy: try clap first (quick, offline), then voice.
        while not result["triggered"]:
            if self.listen_for_clap():
                result["triggered"] = True
                result["source"] = "clap"
                break
            if self.listen_for_wake_word():
                result["triggered"] = True
                result["source"] = "voice"
                break

        if result["triggered"]:
            logger.info(f"Wake trigger: {result['source']}")
        return result["triggered"]

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
                MIN_ENERGY_THRESHOLD, self.recognizer.energy_threshold
            )

            print(
                f"  \033[2m⟫ Energy threshold: "
                f"{self.recognizer.energy_threshold:.0f}\033[0m"
            )
        except Exception as e:
            logger.warning(f"Calibration error: {e}")
            self.recognizer.energy_threshold = MIN_ENERGY_THRESHOLD
            print("  \033[2m⟫ Using default microphone settings\033[0m")
