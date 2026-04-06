"""System commands for J.A.R.V.I.S. — apps, websites, music, system info, etc."""

import datetime
import json
import logging
import os
import platform
import subprocess
import urllib.parse
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

    _NICKNAME_MAP = {
        "chrome": "Google Chrome",
        "imessage": "Messages",
        "texts": "Messages",
        "text": "Messages",
        "settings": "System Settings",
        "system preferences": "System Settings",
        "preferences": "System Settings",
        "vscode": "Visual Studio Code",
        "vs code": "Visual Studio Code",
        "code editor": "Cursor",
        "apple music": "Music",
        "itunes": "Music",
        "zoom": "zoom.us",
        "teams": "Microsoft Teams",
        "word": "Microsoft Word",
        "excel": "Microsoft Excel",
        "powerpoint": "Microsoft PowerPoint",
        "ppt": "Microsoft PowerPoint",
        "outlook": "Microsoft Outlook",
        "email": "Microsoft Outlook",
        "onedrive": "OneDrive",
        "onenote": "Microsoft OneNote",
        "to do": "Microsoft To Do",
        "todos": "Microsoft To Do",
        "vlc": "VLC",
        "obs": "OBS",
        "iterm": "iTerm",
        "utorrent": "uTorrent Web",
        "torrent": "uTorrent Web",
        "quicktime": "QuickTime Player",
        "voice memos": "VoiceMemos",
        "app store": "App Store",
        "find my": "FindMy",
        "photo booth": "Photo Booth",
        "time machine": "Time Machine",
        "chatgpt": "ChatGPT",
        "geforce now": "NVIDIA GeForce NOW",
        "geforce": "NVIDIA GeForce NOW",
        "metatrader": "MetaTrader 5",
        "stocks to trade": "StocksToTrade",
        "djay": "djay Pro",
        "iphone mirroring": "iPhone Mirroring",
        "windsurf": "Windsurf",
        "terminal": "Terminal",
        "finder": "Finder",
        "activity monitor": "Activity Monitor",
        "disk utility": "Disk Utility",
        "console": "Console",
        "keychain": "Keychain Access",
        "screen sharing": "Screen Sharing",
        "bluetooth": "Bluetooth File Exchange",
    }

    _installed_apps = None

    @classmethod
    def _discover_apps(cls):
        """Scan /Applications and /System/Applications for all installed apps."""
        if cls._installed_apps is not None:
            return cls._installed_apps

        apps = {}
        scan_dirs = ["/Applications", "/System/Applications"]

        for scan_dir in scan_dirs:
            try:
                for entry in os.listdir(scan_dir):
                    if entry.endswith(".app"):
                        app_name = entry[:-4]
                        key = app_name.lower()
                        apps[key] = app_name

                        words = key.split()
                        if len(words) > 1:
                            apps[words[-1]] = app_name
                            if words[0] == "microsoft" and len(words) > 1:
                                apps[" ".join(words[1:])] = app_name
            except OSError:
                pass

        for nick, real in cls._NICKNAME_MAP.items():
            apps[nick.lower()] = real

        cls._installed_apps = apps
        logger.info(f"Discovered {len(apps)} app mappings")
        return apps

    def open_application(self, app_name):
        try:
            if self.is_macos:
                apps = self._discover_apps()
                key = app_name.lower().strip()
                actual = apps.get(key)

                if not actual:
                    for k, v in apps.items():
                        if key in k or k in key:
                            actual = v
                            break

                if not actual:
                    actual = app_name

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

    def list_applications(self):
        """List all installed applications."""
        apps = self._discover_apps()
        unique_apps = sorted(set(apps.values()))
        return f"{len(unique_apps)} apps installed: " + ", ".join(unique_apps[:30])

    def close_application(self, app_name):
        """Quit an application by name."""
        try:
            if self.is_macos:
                apps = self._discover_apps()
                actual = apps.get(app_name.lower().strip(), app_name)
                subprocess.run(
                    [
                        "osascript", "-e",
                        f'tell application "{actual}" to quit',
                    ],
                    capture_output=True, timeout=5,
                )
                return f"Closed {actual}"
            return "Not supported on this platform"
        except Exception as e:
            return f"Failed to close {app_name}: {e}"

    # ── Alarms (Clock App) ──────────────────────────────────────

    def set_alarm(self, time_str, label="Alarm"):
        """Set an alarm in the macOS Clock app.

        Args:
            time_str: Time like "4:00 AM", "7:30 PM", "6:15 am"
            label: Optional alarm label
        """
        try:
            if not self.is_macos:
                return "Clock alarms only available on macOS"

            parts = time_str.strip().upper().split()
            time_part = parts[0]
            am_pm = parts[1] if len(parts) > 1 else ""

            if ":" in time_part:
                hour, minute = time_part.split(":")[:2]
            else:
                hour = time_part
                minute = "00"

            hour = hour.zfill(2)
            minute = minute.zfill(2)

            am_key = "a" if am_pm.startswith("A") else "p"
            escaped_label = label.replace('"', '\\"')

            script = f'''
            tell application "Clock" to activate
            delay 0.5

            tell application "System Events"
                tell process "Clock"
                    click radio button 2 of radio group 1 of group 1 of toolbar 1 of window "Clock"
                    delay 0.3
                    perform action "AXPress" of menu button 1 of toolbar 1 of window "Clock"
                    delay 1

                    set s to sheet 1 of window "Clock"
                    set dtArea to UI element 1 of group 1 of s
                    set focused of dtArea to true
                    delay 0.2

                    keystroke "{hour}"
                    delay 0.15
                    key code 48
                    delay 0.15
                    keystroke "{minute}"
                    delay 0.15
                    key code 48
                    delay 0.15
                    keystroke "{am_key}"
                    delay 0.2

                    set value of text field 1 of s to "{escaped_label}"
                    delay 0.2
                    click button "Save" of s
                end tell
            end tell
            '''

            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=15,
            )

            if result.returncode == 0:
                return f"Alarm set for {hour}:{minute} {am_pm} with label '{label}'"
            else:
                logger.error(f"Alarm error: {result.stderr}")
                return f"Failed to set alarm: {result.stderr.strip()}"

        except Exception as e:
            logger.error(f"Alarm error: {e}")
            return f"Failed to set alarm: {e}"

    def delete_alarm(self, time_str):
        """Delete an alarm by its time from the Clock app."""
        try:
            if not self.is_macos:
                return "Clock alarms only available on macOS"

            script = f'''
            tell application "Clock" to activate
            delay 0.5

            tell application "System Events"
                tell process "Clock"
                    click radio button 2 of radio group 1 of group 1 of toolbar 1 of window "Clock"
                    delay 0.3

                    set targetDesc to "{time_str}"
                    set alarmGroups to every group of group 1 of group 1 of group 1 of group 1 of group 1 of group 1 of group 2 of group 1 of group 1 of group 1 of group 1 of group 1 of window "Clock"

                    repeat with ag in alarmGroups
                        try
                            set d to description of ag
                            if d contains targetDesc then
                                -- Right click to get delete option, or use the toggle
                                set value of checkbox 1 of ag to 0
                                return "Disabled alarm at " & targetDesc
                            end if
                        end try
                    end repeat
                    return "No alarm found matching " & targetDesc
                end tell
            end tell
            '''

            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=15,
            )
            return result.stdout.strip() if result.returncode == 0 else f"Error: {result.stderr.strip()}"

        except Exception as e:
            return f"Failed to delete alarm: {e}"

    def list_alarms(self):
        """List all current alarms in the Clock app."""
        try:
            if not self.is_macos:
                return "Clock alarms only available on macOS"

            script = '''
            tell application "Clock" to activate
            delay 0.5

            tell application "System Events"
                tell process "Clock"
                    click radio button 2 of radio group 1 of group 1 of toolbar 1 of window "Clock"
                    delay 0.5

                    set output to ""
                    set allItems to entire contents of window "Clock"
                    repeat with item_ref in allItems
                        try
                            if class of item_ref is button then
                                set d to description of item_ref
                                if d contains "Alarm" then
                                    set output to output & d & " | "
                                end if
                            end if
                        end try
                    end repeat
                    return output
                end tell
            end tell
            '''

            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=15,
            )

            output = result.stdout.strip().rstrip("| ").strip()
            return output if output else "No alarms set"

        except Exception as e:
            return f"Failed to list alarms: {e}"

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

    def play_music(self, query=""):
        """Open Spotify and play music. If a query is given, search and play that song/artist."""
        import time as _time

        try:
            if not self.is_macos:
                return self.open_application("Spotify")

            subprocess.Popen(["open", "-a", "Spotify"])
            _time.sleep(2)

            if query:
                track_uri = self._spotify_search(query)
                if not track_uri:
                    safe_q = query.replace('"', '\\"')
                    track_uri = f"spotify:search:{safe_q}"

                subprocess.run(
                    [
                        "osascript", "-e",
                        f'tell application "Spotify" to play track "{track_uri}"',
                    ],
                    capture_output=True, timeout=5,
                )
                _time.sleep(2)
                info = self.get_current_track()
                return f"Playing: {info}"

            subprocess.run(
                ["osascript", "-e", 'tell application "Spotify" to play'],
                capture_output=True, timeout=5,
            )
            return "Spotify is now playing"
        except Exception as e:
            logger.error(f"Spotify playback error: {e}")
            return f"Opened Spotify but couldn't start playback: {e}"

    def _spotify_search(self, query):
        """Search Spotify's public API and return the top track URI."""
        try:
            token = self._get_spotify_token()
            if not token:
                return None

            encoded_q = urllib.parse.quote(query)
            url = (
                f"https://api.spotify.com/v1/search"
                f"?q={encoded_q}&type=track&limit=1"
            )
            req = urllib.request.Request(
                url, headers={"Authorization": f"Bearer {token}"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())

            tracks = data.get("tracks", {}).get("items", [])
            if tracks:
                track = tracks[0]
                logger.info(
                    f"Spotify search '{query}' → {track['name']} by {track['artists'][0]['name']}"
                )
                return track["uri"]
            return None
        except Exception as e:
            logger.warning(f"Spotify search failed: {e}")
            return None

    def _get_spotify_token(self):
        """Get a Spotify API access token using client credentials (public/anonymous)."""
        try:
            import base64

            client_id = self.config.get("spotify_client_id", default="")
            client_secret = self.config.get("spotify_client_secret", default="")

            if not client_id or not client_secret:
                return None

            auth = base64.b64encode(
                f"{client_id}:{client_secret}".encode()
            ).decode()

            data = urllib.parse.urlencode(
                {"grant_type": "client_credentials"}
            ).encode()
            req = urllib.request.Request(
                "https://accounts.spotify.com/api/token",
                data=data,
                headers={
                    "Authorization": f"Basic {auth}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                token_data = json.loads(resp.read().decode())
            return token_data.get("access_token")
        except Exception as e:
            logger.warning(f"Spotify token error: {e}")
            return None

    def pause_music(self):
        try:
            if self.is_macos:
                subprocess.run(
                    ["osascript", "-e", 'tell application "Spotify" to pause'],
                    capture_output=True, timeout=5,
                )
                return "Music paused"
            return "Not supported on this platform"
        except Exception as e:
            return f"Pause error: {e}"

    def next_track(self):
        try:
            if self.is_macos:
                subprocess.run(
                    ["osascript", "-e", 'tell application "Spotify" to next track'],
                    capture_output=True, timeout=5,
                )
                return "Skipped to next track"
            return "Not supported on this platform"
        except Exception as e:
            return f"Next track error: {e}"

    def previous_track(self):
        try:
            if self.is_macos:
                subprocess.run(
                    ["osascript", "-e", 'tell application "Spotify" to previous track'],
                    capture_output=True, timeout=5,
                )
                return "Playing previous track"
            return "Not supported on this platform"
        except Exception as e:
            return f"Previous track error: {e}"

    def get_current_track(self):
        try:
            if self.is_macos:
                result = subprocess.run(
                    [
                        "osascript", "-e",
                        'tell application "Spotify" to return '
                        '(name of current track) & " by " & '
                        '(artist of current track)',
                    ],
                    capture_output=True, text=True, timeout=5,
                )
                track = result.stdout.strip()
                return f"Now playing: {track}" if track else "Nothing is playing"
            return "Not supported on this platform"
        except Exception as e:
            return f"Track info error: {e}"

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

    # ── iMessage ─────────────────────────────────────────────────

    def send_imessage(self, recipient, message):
        """Send an iMessage to a contact by name or phone number."""
        try:
            if not self.is_macos:
                return "iMessage is only available on macOS"

            escaped_msg = message.replace('"', '\\"')
            escaped_to = recipient.replace('"', '\\"')

            script = f'''
            tell application "Messages"
                set targetService to 1st account whose service type = iMessage
                set targetBuddy to participant "{escaped_to}" of targetService
                send "{escaped_msg}" to targetBuddy
            end tell
            '''

            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=10,
            )

            if result.returncode == 0:
                return f"Message sent to {recipient}"
            else:
                phone = self._resolve_contact(recipient)
                if phone and phone != recipient:
                    return self.send_imessage(phone, message)
                return f"Failed to send message: {result.stderr.strip()}"

        except Exception as e:
            logger.error(f"iMessage error: {e}")
            return f"Failed to send message: {e}"

    def _resolve_contact(self, name):
        """Try to find a phone number or email for a contact name via Contacts.app."""
        try:
            script = f'''
            tell application "Contacts"
                set matchedPeople to (every person whose name contains "{name}")
                if (count of matchedPeople) > 0 then
                    set thePerson to item 1 of matchedPeople
                    try
                        return value of phone 1 of thePerson
                    on error
                        try
                            return value of email 1 of thePerson
                        on error
                            return ""
                        end try
                    end try
                else
                    return ""
                end if
            end tell
            '''
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=10,
            )
            contact = result.stdout.strip()
            if contact:
                logger.info(f"Resolved '{name}' to '{contact}'")
                return contact
            return None
        except Exception as e:
            logger.error(f"Contact lookup error: {e}")
            return None

    def read_imessages(self, contact="", count=3):
        """Read recent iMessages via osascript shell bridge (bypasses Full Disk Access)."""
        try:
            if not self.is_macos:
                return "iMessage is only available on macOS"

            db = os.path.expanduser("~/Library/Messages/chat.db")

            if contact:
                phone = self._resolve_contact(contact) or contact
                escaped = phone.replace("'", "''")
                sql = (
                    "SELECT "
                    "CASE WHEN m.is_from_me=1 THEN 'You' "
                    f"ELSE '{contact}' END, "
                    "m.text, "
                    "datetime(m.date/1000000000+978307200,'unixepoch','localtime') "
                    "FROM message m "
                    "JOIN handle h ON m.handle_id=h.ROWID "
                    f"WHERE h.id LIKE '%{escaped}%' "
                    "AND m.text IS NOT NULL AND m.text!='' "
                    f"ORDER BY m.date DESC LIMIT {count}"
                )
            else:
                sql = (
                    "SELECT "
                    "CASE WHEN m.is_from_me=1 THEN 'You' "
                    "ELSE COALESCE(h.id,'Unknown') END, "
                    "m.text, "
                    "datetime(m.date/1000000000+978307200,'unixepoch','localtime') "
                    "FROM message m "
                    "LEFT JOIN handle h ON m.handle_id=h.ROWID "
                    "WHERE m.text IS NOT NULL AND m.text!='' "
                    f"ORDER BY m.date DESC LIMIT {count}"
                )

            safe_sql = sql.replace('"', '\\"')
            script = f'do shell script "sqlite3 \\"{db}\\" \\"{safe_sql}\\""'

            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=15,
            )

            if result.returncode != 0:
                logger.warning(f"iMessage read error: {result.stderr}")
                return "Couldn't access messages at the moment, sir."

            lines = result.stdout.strip().split("\n")
            if not lines or lines == ['']:
                label = f" from {contact}" if contact else ""
                return f"No recent messages found{label}"

            messages = []
            for line in lines:
                parts = line.split("|", 2)
                if len(parts) >= 2:
                    sender = parts[0].strip()
                    text_val = parts[1].strip()
                    if text_val and len(text_val) < 200:
                        messages.append(f"{sender}: {text_val}")

            return " . ".join(messages) if messages else "No messages found"

        except Exception as e:
            logger.error(f"Read messages error: {e}")
            return f"Failed to read messages: {e}"

    # ── Live News Briefing ───────────────────────────────────────

    NEWS_API_URL = "https://live-news-reporter-production.up.railway.app/api/news"

    def get_news_briefing(self, count=5, category=""):
        """Fetch top stories from the live news API."""
        try:
            url = self.NEWS_API_URL
            req = urllib.request.Request(url, headers={"User-Agent": "Jarvis/2.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                articles = json.loads(resp.read().decode())

            if category:
                cat = category.lower()
                articles = [a for a in articles if a.get("category", "").lower() == cat]

            breaking = [a for a in articles if a.get("is_breaking")]
            if breaking:
                articles = breaking

            top = articles[:count]
            if not top:
                return "No news articles available at the moment"

            summaries = []
            for a in top:
                title = a.get("title", "")
                summary = a.get("summary", "")
                source = a.get("source", "")
                blurb = summary if summary and summary != title else title
                summaries.append(f"[{source}] {blurb}")

            return " || ".join(summaries)
        except Exception as e:
            logger.error(f"News fetch error: {e}")
            return "Unable to fetch news at the moment"

    # ── Outlook Email (Microsoft Graph API) ──────────────────────

    _OUTLOOK_CLIENT_ID = "1950a258-227b-4e31-a9cf-717495945fc2"
    _OUTLOOK_SCOPES = ["Mail.Read", "Mail.ReadBasic", "User.Read"]
    _OUTLOOK_TOKEN_FILE = os.path.expanduser("~/.jarvis/outlook_token.json")

    def _get_outlook_token(self):
        """Get a valid access token for Microsoft Graph, refreshing if needed."""
        import msal

        cache = msal.SerializableTokenCache()
        if os.path.exists(self._OUTLOOK_TOKEN_FILE):
            with open(self._OUTLOOK_TOKEN_FILE) as f:
                cache.deserialize(f.read())

        app = msal.PublicClientApplication(
            self._OUTLOOK_CLIENT_ID,
            authority="https://login.microsoftonline.com/consumers",
            token_cache=cache,
        )

        accounts = app.get_accounts()
        if accounts:
            result = app.acquire_token_silent(self._OUTLOOK_SCOPES, account=accounts[0])
            if result and "access_token" in result:
                if cache.has_state_changed:
                    with open(self._OUTLOOK_TOKEN_FILE, "w") as f:
                        f.write(cache.serialize())
                return result["access_token"]

        return None

    def setup_outlook_auth(self):
        """Interactive device code flow to authenticate with Microsoft."""
        import msal

        cache = msal.SerializableTokenCache()
        app = msal.PublicClientApplication(
            self._OUTLOOK_CLIENT_ID,
            authority="https://login.microsoftonline.com/consumers",
            token_cache=cache,
        )

        flow = app.initiate_device_flow(scopes=self._OUTLOOK_SCOPES)
        if "user_code" not in flow:
            return f"Auth error: {flow.get('error_description', 'Unknown error')}"

        print(f"\n  To sign in to Outlook, go to: {flow['verification_uri']}")
        print(f"  Enter code: {flow['user_code']}")
        print(f"  Waiting for you to sign in...\n")

        result = app.acquire_token_by_device_flow(flow)

        if "access_token" in result:
            with open(self._OUTLOOK_TOKEN_FILE, "w") as f:
                f.write(cache.serialize())
            os.chmod(self._OUTLOOK_TOKEN_FILE, 0o600)
            return "Outlook authenticated successfully"
        else:
            return f"Auth failed: {result.get('error_description', 'Unknown error')}"

    def check_outlook_emails(self, count=5, days=5):
        """Check recent emails from Outlook via Microsoft Graph API."""
        try:
            token = self._get_outlook_token()
            if not token:
                return (
                    "Outlook not authenticated. Run python3 Jarvis.py --setup-email "
                    "to sign in, or say 'setup email' to start the process."
                )

            from datetime import timedelta
            cutoff = (datetime.datetime.now() - timedelta(days=days)).strftime(
                "%Y-%m-%dT00:00:00Z"
            )

            url = (
                "https://graph.microsoft.com/v1.0/me/messages"
                f"?$top={count}"
                f"&$orderby=receivedDateTime desc"
                f"&$filter=receivedDateTime ge {cutoff}"
                "&$select=subject,from,receivedDateTime,isRead,bodyPreview"
            )

            req = urllib.request.Request(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )

            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            messages = data.get("value", [])
            if not messages:
                return "No emails in the last 5 days, sir. Inbox is quiet."

            unread = sum(1 for m in messages if not m.get("isRead", True))
            summaries = []
            for m in messages:
                sender = m.get("from", {}).get("emailAddress", {}).get("name", "Unknown")
                subject = m.get("subject", "No subject")
                read_status = "" if m.get("isRead") else " [UNREAD]"
                received = m.get("receivedDateTime", "")[:10]
                summaries.append(f"{sender}: {subject}{read_status} ({received})")

            header = f"{len(messages)} emails, {unread} unread"
            return header + " | " + " | ".join(summaries)

        except urllib.error.HTTPError as e:
            if e.code == 401:
                return "Outlook token expired. Say 'setup email' to re-authenticate."
            logger.error(f"Graph API error: {e}")
            return f"Email check failed: {e}"
        except Exception as e:
            logger.error(f"Outlook error: {e}")
            return f"Failed to check email: {e}"

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
