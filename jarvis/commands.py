"""System commands for J.A.R.V.I.S. — apps, websites, music, system info, etc."""

import datetime
import json
import logging
import os
import platform
import subprocess
import urllib.request

logger = logging.getLogger("jarvis.commands")


class JarvisCommands:
    def __init__(self, config):
        self.config = config
        self.is_macos = platform.system() == "Darwin"
        self.is_windows = platform.system() == "Windows"

    # ── Time & Date ─────────────────────────────────────────────

    def get_time(self):
        return datetime.datetime.now().strftime("%I:%M %p")

    def get_date(self):
        return datetime.datetime.now().strftime("%A, %B %d, %Y")

    def get_greeting(self):
        hour = datetime.datetime.now().hour
        name = self.config.get("user_name", default="sir")
        if 5 <= hour < 12:
            return f"Good morning, {name}"
        elif 12 <= hour < 17:
            return f"Good afternoon, {name}"
        elif 17 <= hour < 21:
            return f"Good evening, {name}"
        else:
            return f"Good evening, {name}. Burning the midnight oil, are we?"

    # ── Applications ────────────────────────────────────────────

    _MACOS_APP_MAP = {
        "spotify": "Spotify",
        "safari": "Safari",
        "firefox": "Firefox",
        "chrome": "Google Chrome",
        "google chrome": "Google Chrome",
        "notes": "Notes",
        "calendar": "Calendar",
        "messages": "Messages",
        "imessage": "Messages",
        "mail": "Mail",
        "finder": "Finder",
        "terminal": "Terminal",
        "iterm": "iTerm",
        "settings": "System Settings",
        "system preferences": "System Settings",
        "system settings": "System Settings",
        "maps": "Maps",
        "photos": "Photos",
        "music": "Music",
        "apple music": "Music",
        "discord": "Discord",
        "slack": "Slack",
        "vscode": "Visual Studio Code",
        "visual studio code": "Visual Studio Code",
        "code": "Visual Studio Code",
        "cursor": "Cursor",
        "xcode": "Xcode",
        "zoom": "zoom.us",
        "teams": "Microsoft Teams",
        "word": "Microsoft Word",
        "excel": "Microsoft Excel",
        "powerpoint": "Microsoft PowerPoint",
        "notion": "Notion",
        "obsidian": "Obsidian",
        "telegram": "Telegram",
        "whatsapp": "WhatsApp",
        "facetime": "FaceTime",
        "preview": "Preview",
        "activity monitor": "Activity Monitor",
        "calculator": "Calculator",
        "clock": "Clock",
    }

    def open_application(self, app_name):
        try:
            if self.is_macos:
                actual = self._MACOS_APP_MAP.get(app_name.lower(), app_name)
                subprocess.Popen(["open", "-a", actual])
                return f"Opened {actual}"
            elif self.is_windows:
                subprocess.Popen(f"start {app_name}", shell=True)
                return f"Opened {app_name}"
            else:
                subprocess.Popen([app_name.lower()])
                return f"Opened {app_name}"
        except Exception as e:
            logger.error(f"Failed to open {app_name}: {e}")
            return f"Failed to open {app_name}: {e}"

    # ── Websites ────────────────────────────────────────────────

    def open_website(self, url):
        if not url.startswith(("http://", "https://")):
            if "." not in url:
                url = f"https://www.{url}.com"
            else:
                url = "https://" + url
        try:
            if self.is_macos:
                subprocess.Popen(["open", url])
            elif self.is_windows:
                os.startfile(url)
            else:
                subprocess.Popen(["xdg-open", url])
            return f"Opened {url}"
        except Exception as e:
            logger.error(f"Failed to open website: {e}")
            return f"Failed to open {url}: {e}"

    # ── Music ───────────────────────────────────────────────────

    def play_music(self):
        return self.open_application("Spotify")

    # ── Weather ─────────────────────────────────────────────────

    def get_weather(self, location=""):
        try:
            url = f"https://wttr.in/{location}?format=j1"
            req = urllib.request.Request(url, headers={"User-Agent": "Jarvis/2.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())

            current = data.get("current_condition", [{}])[0]
            area = data.get("nearest_area", [{}])[0]
            city = area.get("areaName", [{}])[0].get("value", "your area")

            temp_f = current.get("temp_F", "N/A")
            temp_c = current.get("temp_C", "N/A")
            desc = current.get("weatherDesc", [{}])[0].get("value", "Unknown")
            humidity = current.get("humidity", "N/A")
            feels_f = current.get("FeelsLikeF", "N/A")

            return (
                f"Weather in {city}: {desc}, {temp_f}°F ({temp_c}°C), "
                f"feels like {feels_f}°F, humidity {humidity}%"
            )
        except Exception as e:
            logger.error(f"Weather error: {e}")
            return "Unable to fetch weather data at the moment"

    # ── System Info ─────────────────────────────────────────────

    def get_system_info(self):
        info = []
        try:
            if self.is_macos:
                try:
                    out = subprocess.run(
                        ["pmset", "-g", "batt"],
                        capture_output=True, text=True, timeout=5,
                    ).stdout
                    for line in out.split("\n"):
                        if "%" in line:
                            info.append(f"Battery: {line.strip()}")
                            break
                except Exception:
                    pass

                try:
                    out = subprocess.run(
                        ["uptime"], capture_output=True, text=True, timeout=5
                    ).stdout.strip()
                    info.append(f"Uptime: {out}")
                except Exception:
                    pass

                try:
                    out = subprocess.run(
                        ["df", "-h", "/"],
                        capture_output=True, text=True, timeout=5,
                    ).stdout.strip().split("\n")
                    if len(out) > 1:
                        parts = out[1].split()
                        info.append(f"Disk: {parts[3]} available of {parts[1]}")
                except Exception:
                    pass

            return " | ".join(info) if info else "System diagnostics unavailable"
        except Exception as e:
            return f"System info error: {e}"

    # ── Volume ──────────────────────────────────────────────────

    def set_volume(self, level):
        try:
            if self.is_macos:
                vol = max(0, min(100, int(level)))
                subprocess.run(
                    ["osascript", "-e", f"set volume output volume {vol}"],
                    check=True, capture_output=True,
                )
                return f"Volume set to {vol}%"
            return "Volume control not available on this platform"
        except Exception as e:
            return f"Failed to set volume: {e}"

    # ── Web Search ──────────────────────────────────────────────

    def search_web(self, query):
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        self.open_website(url)
        return f"Searching the web for: {query}"

    # ── Notifications ───────────────────────────────────────────

    def send_notification(self, title, message):
        try:
            if self.is_macos:
                script = (
                    f'display notification "{message}" '
                    f'with title "{title}" sound name "Glass"'
                )
                subprocess.run(
                    ["osascript", "-e", script],
                    check=True, capture_output=True,
                )
                return f"Notification sent: {title}"
            return "Notifications not supported on this platform"
        except Exception as e:
            return f"Notification error: {e}"

    # ── Clipboard ───────────────────────────────────────────────

    def copy_to_clipboard(self, text):
        try:
            if self.is_macos:
                process = subprocess.Popen(
                    ["pbcopy"], stdin=subprocess.PIPE
                )
                process.communicate(text.encode())
                return "Copied to clipboard"
            return "Clipboard not supported on this platform"
        except Exception as e:
            return f"Clipboard error: {e}"

    # ── Screenshot ──────────────────────────────────────────────

    def take_screenshot(self):
        try:
            if self.is_macos:
                path = os.path.expanduser(
                    f"~/Desktop/jarvis_screenshot_{datetime.datetime.now():%Y%m%d_%H%M%S}.png"
                )
                subprocess.run(
                    ["screencapture", "-x", path],
                    check=True, capture_output=True,
                )
                return f"Screenshot saved to {path}"
            return "Screenshots not supported on this platform"
        except Exception as e:
            return f"Screenshot error: {e}"

    # ── Lock Computer ───────────────────────────────────────────

    def lock_computer(self):
        try:
            if self.is_macos:
                subprocess.run(
                    [
                        "osascript", "-e",
                        'tell application "System Events" to keystroke "q" '
                        'using {command down, control down}',
                    ],
                    check=True, capture_output=True,
                )
                return "Screen locked"
            elif self.is_windows:
                subprocess.run("rundll32.exe user32.dll,LockWorkStation", shell=True)
                return "Screen locked"
            else:
                subprocess.run(["xdg-screensaver", "lock"], capture_output=True)
                return "Screen locked"
        except Exception as e:
            logger.error(f"Lock error: {e}")
            return f"Failed to lock screen: {e}"

    # ── CPU Usage ───────────────────────────────────────────────

    def get_cpu_usage(self):
        try:
            if self.is_macos:
                out = subprocess.run(
                    ["top", "-l", "1", "-n", "0", "-stats", "cpu"],
                    capture_output=True, text=True, timeout=10,
                ).stdout
                for line in out.split("\n"):
                    if "CPU usage" in line:
                        return line.strip()
                return None
            return None
        except Exception:
            return None

    # ── Battery (compact) ───────────────────────────────────────

    def get_battery_percent(self):
        try:
            if self.is_macos:
                out = subprocess.run(
                    ["pmset", "-g", "batt"],
                    capture_output=True, text=True, timeout=5,
                ).stdout
                for line in out.split("\n"):
                    if "%" in line:
                        start = line.index("\t") + 1 if "\t" in line else 0
                        pct_end = line.index("%") + 1
                        return line[start:pct_end].strip()
                return None
            return None
        except Exception:
            return None

    # ── Compact Status (for periodic ambient reports) ───────────

    def compact_status(self):
        """One-liner status suitable for ambient voice report."""
        parts = []

        cpu = self.get_cpu_usage()
        if cpu:
            parts.append(cpu)

        batt = self.get_battery_percent()
        if batt:
            parts.append(f"Battery {batt}")

        try:
            out = subprocess.run(
                ["df", "-h", "/"],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip().split("\n")
            if len(out) > 1:
                disk_parts = out[1].split()
                parts.append(f"Disk {disk_parts[3]} free")
        except Exception:
            pass

        return ", ".join(parts) if parts else "All systems nominal"

    # ── Brightness ──────────────────────────────────────────────

    def set_brightness(self, level):
        try:
            if self.is_macos:
                val = max(0.0, min(1.0, level / 100.0))
                subprocess.run(
                    [
                        "osascript", "-e",
                        f'tell application "System Events" to set value of slider 1 '
                        f'of group 1 of window "Display" of application process '
                        f'"System Preferences" to {val}',
                    ],
                    capture_output=True,
                )
                return f"Brightness adjusted to {level}%"
            return "Brightness control not available"
        except Exception as e:
            return f"Brightness error: {e}"
