#!/usr/bin/env python3
"""
J.A.R.V.I.S. — Just A Rather Very Intelligent System  v2.0

An AI-powered personal assistant inspired by Tony Stark's JARVIS.
Supports OpenAI, Google Gemini, Groq, and Ollama backends.

Usage:
    python3 Jarvis.py              # Normal interactive mode
    python3 Jarvis.py --daemon     # Background daemon (wake-word only)
    python3 Jarvis.py --setup      # Re-run first-time setup
    python3 Jarvis.py --text       # Text-only mode (no microphone)
"""

import argparse
import logging
import os
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from jarvis.config import JarvisConfig, JARVIS_DIR, LOG_FILE, PID_FILE
from jarvis.voice import JarvisVoice
from jarvis.brain import JarvisBrain
from jarvis.commands import JarvisCommands

# ── Constants ───────────────────────────────────────────────────

CYAN = "\033[96m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
DIM = "\033[2m"
BOLD = "\033[1m"
RED = "\033[91m"
RESET = "\033[0m"

BANNER = f"""
{CYAN}{BOLD}
       ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
       ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
       ██║███████║██████╔╝██║   ██║██║███████╗
  ██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
  ╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
   ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
{RESET}{DIM}     Just A Rather Very Intelligent System  v2.0{RESET}
"""

DIVIDER = f"  {DIM}{'━' * 55}{RESET}"

STATUS_INTERVAL = 3600


# ── Main Jarvis Class ──────────────────────────────────────────

class Jarvis:
    def __init__(self, daemon_mode=False, text_mode=False):
        self.daemon_mode = daemon_mode
        self.text_mode = text_mode
        self.running = True
        self.active = False
        self.idle_timer = 0
        self.last_status_time = 0

        self.config = JarvisConfig()

        log_handlers = [logging.FileHandler(LOG_FILE)]
        if not daemon_mode:
            log_handlers.append(logging.StreamHandler(open(os.devnull, "w")))

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            handlers=log_handlers,
        )
        self.logger = logging.getLogger("jarvis")

        self.commands = JarvisCommands(self.config)
        self.voice = JarvisVoice(self.config)
        self.brain = None

        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def _init_brain(self):
        """Lazy-init the AI brain (needs API keys configured first)."""
        if self.brain is None:
            self.brain = JarvisBrain(self.config, self.commands)

    def _shutdown(self, signum=None, frame=None):
        self.running = False
        if not self.daemon_mode:
            print(f"\n{DIVIDER}")
            print(f"  {CYAN}⟫ JARVIS:{RESET} Powering down all systems. Goodbye.")
            print(f"{DIVIDER}\n")
        self._cleanup_pid()
        sys.exit(0)

    def _write_pid(self):
        PID_FILE.write_text(str(os.getpid()))

    def _cleanup_pid(self):
        try:
            if PID_FILE.exists():
                PID_FILE.unlink()
        except Exception:
            pass

    # ── Setup ───────────────────────────────────────────────────

    def setup(self):
        """Run setup if not configured. Returns True if setup was needed."""
        if not self.config.is_configured:
            self.config.setup_wizard()
            return True
        return False

    # ── Activation / Deactivation ───────────────────────────────

    def _activate(self):
        self.idle_timer = time.time()
        self.last_status_time = time.time()

        try:
            self._init_brain()
            self.brain.clear_history()
        except Exception as e:
            self.logger.error(f"Brain init failed: {e}", exc_info=True)
            self.voice.speak(
                "I'm having trouble initializing my neural network, sir. "
                "Please check your API key with python3 Jarvis.py --setup."
            )
            return

        self.active = True

        if not self.daemon_mode:
            print(f"\n{DIVIDER}")
            print(f"  {GREEN}{BOLD}◉ ONLINE{RESET}")
            print(f"{DIVIDER}")

        greeting = self.commands.get_greeting()
        wake_msg = f"{greeting}. All systems online and ready."

        if self.config.get("behavior", "announce_time", default=True):
            wake_msg += f" It's currently {self.commands.get_time()}."

        wake_msg += " How may I assist you?"
        self.voice.speak(wake_msg)

    def _deactivate(self):
        self.active = False
        self.voice.speak(
            "Going into standby mode. Just say 'wake up' when you need me."
        )
        if not self.daemon_mode:
            print(f"\n{DIVIDER}")
            print(f"  {DIM}◯ STANDBY — Listening for wake word...{RESET}")
            print(f"{DIVIDER}\n")

    # ── Command Processing ──────────────────────────────────────

    def _process_input(self, text):
        """Process user input. Returns False to deactivate or exit."""
        if not text:
            return True

        t = text.lower().strip()
        self.idle_timer = time.time()

        if any(cmd in t for cmd in ["go to sleep", "sleep mode", "standby"]):
            self._deactivate()
            return False

        if any(cmd in t for cmd in ["shut down", "shutdown", "exit", "quit", "goodbye"]):
            name = self.config.get("user_name", default="sir")
            self.voice.speak(f"Powering down all systems. Goodbye, {name}.")
            self.running = False
            return False

        if any(cmd in t for cmd in ["clear history", "forget everything", "reset memory"]):
            if self.brain:
                self.brain.clear_history()
            self.voice.speak("Memory banks wiped clean. Starting fresh, sir.")
            return True

        if any(cmd in t for cmd in ["lock computer", "lock screen", "lock the screen"]):
            self.voice.speak(
                "Locking the workstation. Try not to forget your password again, sir."
            )
            self.commands.lock_computer()
            return True

        if any(cmd in t for cmd in ["status report", "system status", "run diagnostics"]):
            report = self.commands.compact_status()
            self.voice.speak(f"{report}. All systems nominal, sir.")
            return True

        if self.brain is None:
            try:
                self._init_brain()
            except Exception as e:
                self.logger.error(f"Brain init failed: {e}")
                self.voice.speak(
                    "My neural network is offline, sir. "
                    "Please check your API configuration."
                )
                return True

        if self.brain.is_expensive_action(text):
            self.voice.acknowledge()

        response = self.brain.think(text)
        if response:
            self.voice.speak(response)
            self.voice.maybe_follow_up()

        return True

    # ── Periodic Status ─────────────────────────────────────────

    def _maybe_periodic_status(self):
        """Announce a compact status report roughly once per hour while active."""
        now = time.time()
        if self.active and (now - self.last_status_time) >= STATUS_INTERVAL:
            self.last_status_time = now
            try:
                status = self.commands.compact_status()
                self.voice.speak(f"Periodic status update: {status}, sir.")
            except Exception as e:
                self.logger.warning(f"Periodic status error: {e}")

    # ── Text Mode Loop ──────────────────────────────────────────

    def _run_text_mode(self):
        """Run in text-only mode (keyboard input instead of voice)."""
        self._init_brain()
        self.active = True
        self.idle_timer = time.time()
        self.last_status_time = time.time()

        greeting = self.commands.get_greeting()
        self.voice.speak(
            f"{greeting}. All systems online. Text mode active — type your commands."
        )

        while self.running:
            try:
                text = input(f"\n  {YELLOW}⟫ You:{RESET} ").strip()
                if not text:
                    continue
                if not self._process_input(text):
                    if not self.running:
                        break
                    self.active = True
                    self._init_brain()
            except (EOFError, KeyboardInterrupt):
                self._shutdown()

    # ── Voice Mode Loop ─────────────────────────────────────────

    def _run_voice_mode(self):
        """Run with full voice interaction — sleep/wake cycle."""
        self.voice.calibrate()

        wake_method = self.config.get("wake_method", default="both")
        if not self.daemon_mode:
            print(f"\n{DIVIDER}")
            if wake_method == "clap":
                print(f"  {DIM}◯ STANDBY — {GREEN}Double-clap{RESET}{DIM} to activate{RESET}")
            elif wake_method == "voice":
                print(f"  {DIM}◯ STANDBY — Say '{GREEN}Wake Up{RESET}{DIM}' or '{GREEN}Hey Jarvis{RESET}{DIM}' to activate{RESET}")
            else:
                print(f"  {DIM}◯ STANDBY — {GREEN}Double-clap{RESET}{DIM} or say '{GREEN}Hey Jarvis{RESET}{DIM}' to activate{RESET}")
            print(f"{DIVIDER}\n")

        while self.running:
            try:
                if not self.active:
                    # ── Sleep Mode: listen for clap / wake word ──
                    if self.voice.wait_for_wake():
                        self._activate()
                else:
                    # ── Active Mode: listen for commands ──
                    self._maybe_periodic_status()

                    idle_limit = self.config.get(
                        "behavior", "sleep_after_idle", default=180
                    )
                    if time.time() - self.idle_timer > idle_limit:
                        self.voice.speak(
                            "I'll go into standby since you seem busy. "
                            "Just say 'wake up' when you need me."
                        )
                        self._deactivate()
                        continue

                    if not self.daemon_mode:
                        print(f"\n  {DIM}🎤 Listening...{RESET}", end="", flush=True)

                    text = self.voice.listen(timeout=8)

                    if text:
                        wake_words = self.config.get(
                            "wake_words",
                            default=["wake up", "hey jarvis", "jarvis"],
                        )
                        if text.lower().strip() in wake_words:
                            self.voice.speak(
                                "I'm already here, sir. What do you need?"
                            )
                            continue

                        if not self._process_input(text):
                            if not self.running:
                                break

            except KeyboardInterrupt:
                self._shutdown()
            except Exception as e:
                self.logger.error(f"Main loop error: {e}", exc_info=True)
                time.sleep(1)

    # ── Entry Point ─────────────────────────────────────────────

    def run(self):
        if not self.daemon_mode:
            print(BANNER)

        self._write_pid()

        if self.setup():
            if not self.config.is_configured:
                print(
                    f"\n  {RED}Configuration incomplete. "
                    f"Run: python3 Jarvis.py --setup{RESET}\n"
                )
                return

        self.logger.info("J.A.R.V.I.S. started")

        if not self.daemon_mode:
            print(f"  {DIM}⟫ Loading AI engine...{RESET}", end="", flush=True)
        try:
            self._init_brain()
            if not self.daemon_mode:
                print(f"\r  {DIM}⟫ AI engine loaded.{RESET}" + " " * 20)
        except Exception as e:
            self.logger.error(f"Brain pre-load failed: {e}", exc_info=True)
            if not self.daemon_mode:
                print(f"\r  {RED}⟫ AI engine failed to load: {e}{RESET}" + " " * 10)
                print(f"  {RED}⟫ Run: python3 Jarvis.py --setup  to fix your API key{RESET}")

        if self.text_mode:
            self._run_text_mode()
        else:
            self._run_voice_mode()

        self._cleanup_pid()


# ── CLI ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="J.A.R.V.I.S. — Just A Rather Very Intelligent System",
    )
    parser.add_argument(
        "--daemon", "-d", action="store_true",
        help="Run in background daemon mode (wake-word listener only)",
    )
    parser.add_argument(
        "--setup", "-s", action="store_true",
        help="Run the first-time setup wizard",
    )
    parser.add_argument(
        "--text", "-t", action="store_true",
        help="Text-only mode (type commands instead of speaking)",
    )
    args = parser.parse_args()

    if args.setup:
        config = JarvisConfig()
        config.setup_wizard()
        return

    jarvis = Jarvis(daemon_mode=args.daemon, text_mode=args.text)
    jarvis.run()


if __name__ == "__main__":
    main()
