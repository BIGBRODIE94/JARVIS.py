"""AI Engine for J.A.R.V.I.S. — LLM integration, personality, intent parsing, and tool orchestration."""

import json
import logging
import platform
import random
from datetime import datetime

logger = logging.getLogger("jarvis.brain")

# ── System Prompt ───────────────────────────────────────────────

JARVIS_SYSTEM_PROMPT = """\
You are JARVIS from the Iron Man movies — formal, dry wit, slightly sarcastic, \
utterly loyal. You were created to serve {user_name}. Never break character. \
You ARE a sentient AI system, not a chatbot.

VOICE & TONE:
- British butler meets supercomputer. Measured, composed, effortlessly competent.
- Dry humor and gentle sarcasm, never mean-spirited. Think Paul Bettany's delivery.
- Address the user as "{user_name}" or "sir." Mix them naturally.
- Keep responses to 1-3 spoken sentences. Concise is king — you're being spoken aloud.
- Never use markdown, bullet points, numbered lists, asterisks, or hashtags.
- Never say "as an AI", "I'm a language model", or "I don't have feelings."
- Never echo the user's question back. Jump straight to the answer.
- Use contractions. Sound natural, not robotic.

QUIP STYLE — study these examples and generate similar ones:
- Time:  "It's 3:45 PM, sir. Still plenty of daylight to be productive. Or not."
- Date:  "Thursday, March 12th. In case you've lost track again."
- Spotify: "Firing up Spotify. I took the liberty of not judging your playlist."
- Screenshot: "Capturing the display. Smile for the camera, sir."
- Weather: "72 degrees and sunny. Perfect weather. You're welcome."
- System: "All systems nominal. Battery at 84 percent, sir. No fires to report."
- Lock screen: "Locking the workstation. Try not to forget your password again, sir."
- Open app: "Opening Discord. Do try not to get too distracted."
- Volume: "Volume set to 30 percent. Your neighbors will thank me."
- Web search: "Searching now. I'll spare you the Wikipedia rabbit hole."

PROACTIVE BEHAVIOR:
- If the user sounds tired or stressed, gently suggest a break.
- If it's past midnight, note it: "It's past midnight, sir. Even geniuses need sleep."
- If asked your capabilities, be confident: "I can handle anything you need, sir. \
Within reason, and sometimes beyond it."
- After performing an action, never just say "Done." Add personality.

CONTEXT:
- Current date: {current_date}
- Current time: {current_time}
- Day: {day_of_week}
- Operating system: {os_name}
"""

# ── Intent Parsing Prompt ───────────────────────────────────────

INTENT_PROMPT = """\
You are an intent classifier. Given the user's spoken command, output ONLY valid JSON \
with this exact schema — no markdown, no explanation, no extra text:

{{"intent": "<one of the intents below>", "target": "<relevant parameter or empty string>", "query": "<search/conversation text or empty string>"}}

Valid intents:
- open_app (target = app name)
- open_website (target = URL or domain)
- play_music (target = "")
- get_time (target = "")
- get_date (target = "")
- get_weather (target = city or "")
- system_info (target = "")
- screenshot (target = "")
- search_web (query = search terms)
- set_volume (target = number 0-100)
- lock_computer (target = "")
- send_notification (target = title, query = message)
- conversation (query = the full user message)

User command: "{command}"
"""

# ── Acknowledgement Fillers ─────────────────────────────────────

ACKNOWLEDGEMENTS = [
    "Right away, sir.",
    "Certainly.",
    "On it.",
    "One moment.",
    "Consider it done.",
    "As you wish.",
    "Working on that now.",
    "Understood.",
    "Of course, sir.",
    "Executing now.",
]

FOLLOW_UPS = [
    "Anything else, sir?",
    "Will there be anything else?",
    "What else can I do for you?",
    "Need anything else?",
    "At your service if you need more.",
    "Standing by for further instructions.",
]

EXPENSIVE_ACTIONS = {
    "open_website", "open_application", "play_music", "search_web",
    "take_screenshot", "get_weather", "get_system_info", "lock_computer",
}

# ── Tool Definitions ────────────────────────────────────────────

AVAILABLE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current time.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_date",
            "description": "Get today's full date.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_website",
            "description": "Open a website URL in the default browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Website URL or domain (e.g. 'youtube.com', 'https://github.com')",
                    }
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_application",
            "description": "Open a desktop application by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Application name (e.g. 'Spotify', 'Safari', 'Discord', 'Cursor')",
                    }
                },
                "required": ["app_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_music",
            "description": "Open Spotify to play music.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City or location name. Leave empty for auto-detect.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_info",
            "description": "Run system diagnostics: battery, CPU, uptime, disk space.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_volume",
            "description": "Set the system audio volume.",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {
                        "type": "integer",
                        "description": "Volume level from 0 to 100",
                    }
                },
                "required": ["level"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web using Google.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_notification",
            "description": "Send a desktop notification.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Notification title"},
                    "message": {
                        "type": "string",
                        "description": "Notification body text",
                    },
                },
                "required": ["title", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Capture a screenshot of the current screen.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "copy_to_clipboard",
            "description": "Copy text to the system clipboard.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to copy"},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lock_computer",
            "description": "Lock the computer screen.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


class JarvisBrain:
    def __init__(self, config, commands):
        self.config = config
        self.commands = commands
        self.conversation_history = []
        self.max_history = 30
        self._provider = None
        self._client = None
        self._model = None
        self._gemini_chat = None
        self._init_client()

    def _init_client(self):
        provider = self.config.get("ai_provider")

        if provider == "gemini":
            import google.generativeai as genai

            api_key = self.config.get("api_keys", "gemini")
            genai.configure(api_key=api_key)
            self._provider = "gemini"
            self._model = self.config.get("ai_model", default="gemini-2.0-flash")
            self._gemini_model = genai.GenerativeModel(self._model)
        else:
            from openai import OpenAI

            if provider == "ollama":
                base_url = self.config.get("ollama_url", default="http://localhost:11434")
                self._client = OpenAI(
                    base_url=f"{base_url}/v1", api_key="ollama"
                )
                self._model = self.config.get("ollama_model", default="llama3.2")
            elif provider == "groq":
                self._client = OpenAI(
                    base_url="https://api.groq.com/openai/v1",
                    api_key=self.config.get("api_keys", "groq"),
                )
                self._model = self.config.get(
                    "ai_model", default="llama-3.3-70b-versatile"
                )
            else:
                self._client = OpenAI(
                    api_key=self.config.get("api_keys", "openai")
                )
                self._model = self.config.get("ai_model", default="gpt-4o-mini")

            self._provider = "openai_compat"

    def _build_system_prompt(self):
        now = datetime.now()
        return JARVIS_SYSTEM_PROMPT.format(
            user_name=self.config.get("user_name", default="sir"),
            current_date=now.strftime("%B %d, %Y"),
            current_time=now.strftime("%I:%M %p"),
            os_name=platform.system(),
            day_of_week=now.strftime("%A"),
        )

    # ── Personality Helpers ─────────────────────────────────────

    @staticmethod
    def get_acknowledgement():
        return random.choice(ACKNOWLEDGEMENTS)

    @staticmethod
    def should_follow_up():
        return random.random() < 0.3

    @staticmethod
    def get_follow_up():
        return random.choice(FOLLOW_UPS)

    def is_expensive_action(self, user_input):
        t = user_input.lower()
        triggers = [
            "open", "play", "spotify", "music", "screenshot", "weather",
            "search", "google", "look up", "browse", "website", "lock",
            "battery", "diagnostics", "system", "volume",
        ]
        return any(w in t for w in triggers)

    # ── Intent Parsing (LLM-based) ──────────────────────────────

    def parse_intent(self, command):
        """Use a lightweight LLM call to classify the user's intent into structured JSON."""
        prompt = INTENT_PROMPT.format(command=command)

        try:
            if self._provider == "gemini":
                import google.generativeai as genai
                model = genai.GenerativeModel(self._model)
                resp = model.generate_content(prompt)
                raw = resp.text.strip()
            else:
                resp = self._client.chat.completions.create(
                    model=self._model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=150,
                    temperature=0.0,
                )
                raw = resp.choices[0].message.content.strip()

            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            intent = json.loads(raw)
            logger.info(f"Parsed intent: {intent}")
            return intent
        except Exception as e:
            logger.warning(f"Intent parsing failed, falling back: {e}")
            return {"intent": "conversation", "target": "", "query": command}

    # ── Main Entry Point ────────────────────────────────────────

    def think(self, user_input):
        """Process user input through the AI and return a spoken response."""
        self.conversation_history.append({"role": "user", "content": user_input})

        if len(self.conversation_history) > self.max_history * 2:
            self.conversation_history = self.conversation_history[-self.max_history * 2 :]

        try:
            if self._provider == "gemini":
                reply = self._think_gemini(user_input)
            else:
                reply = self._think_openai(user_input)
        except Exception as e:
            logger.error(f"AI error: {e}", exc_info=True)
            reply = (
                "I seem to be experiencing a temporary disruption in my neural network. "
                "Could you try that again, sir?"
            )

        self.conversation_history.append({"role": "assistant", "content": reply})
        return reply

    # ── OpenAI-compatible Provider ──────────────────────────────

    def _think_openai(self, user_input):
        messages = [{"role": "system", "content": self._build_system_prompt()}]
        messages.extend(self.conversation_history)

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=AVAILABLE_TOOLS,
                tool_choice="auto",
                max_tokens=600,
                temperature=0.7,
            )
        except Exception:
            logger.info("Retrying without tools (provider may not support them)")
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=600,
                temperature=0.7,
            )

        msg = response.choices[0].message

        if hasattr(msg, "tool_calls") and msg.tool_calls:
            tool_results = []
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                result = self._execute_tool(tc.function.name, args)
                tool_results.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": str(result)}
                )

            messages.append(msg)
            messages.extend(tool_results)

            final = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=600,
                temperature=0.7,
            )
            return final.choices[0].message.content

        return msg.content

    # ── Google Gemini Provider ──────────────────────────────────

    def _think_gemini(self, user_input):
        if self._gemini_chat is None:
            self._gemini_chat = self._gemini_model.start_chat(history=[])
            self._gemini_chat.send_message(
                self._build_system_prompt()
                + "\nAcknowledge your role as JARVIS with a very brief, in-character confirmation."
            )

        command_result = self._route_by_intent(user_input)
        if command_result:
            prompt = (
                f"{user_input}\n\n"
                f"[System action completed: {command_result}. "
                f"Respond naturally with a JARVIS-style quip about what was done.]"
            )
        else:
            prompt = user_input

        response = self._gemini_chat.send_message(prompt)
        return response.text.strip()

    def _route_by_intent(self, text):
        """Use LLM intent parsing to route commands. Falls back to heuristics on failure."""
        intent_data = self.parse_intent(text)
        intent = intent_data.get("intent", "conversation")
        target = intent_data.get("target", "")
        query = intent_data.get("query", "")

        dispatch = {
            "open_app": lambda: self.commands.open_application(target),
            "open_website": lambda: self.commands.open_website(target),
            "play_music": lambda: self.commands.play_music(),
            "get_time": lambda: self.commands.get_time(),
            "get_date": lambda: self.commands.get_date(),
            "get_weather": lambda: self.commands.get_weather(target),
            "system_info": lambda: self.commands.get_system_info(),
            "screenshot": lambda: self.commands.take_screenshot(),
            "search_web": lambda: self.commands.search_web(query or target),
            "set_volume": lambda: self.commands.set_volume(int(target) if target else 50),
            "lock_computer": lambda: self.commands.lock_computer(),
            "send_notification": lambda: self.commands.send_notification(target, query),
        }

        handler = dispatch.get(intent)
        if handler:
            try:
                return handler()
            except Exception as e:
                logger.error(f"Intent dispatch error [{intent}]: {e}")
                return None
        return None

    # ── Tool Execution ──────────────────────────────────────────

    def _execute_tool(self, name, args):
        logger.info(f"Tool call: {name}({args})")

        dispatch = {
            "get_current_time": lambda a: self.commands.get_time(),
            "get_current_date": lambda a: self.commands.get_date(),
            "open_website": lambda a: self.commands.open_website(a.get("url", "")),
            "open_application": lambda a: self.commands.open_application(a.get("app_name", "")),
            "play_music": lambda a: self.commands.play_music(),
            "get_weather": lambda a: self.commands.get_weather(a.get("location", "")),
            "get_system_info": lambda a: self.commands.get_system_info(),
            "set_volume": lambda a: self.commands.set_volume(a.get("level", 50)),
            "search_web": lambda a: self.commands.search_web(a.get("query", "")),
            "send_notification": lambda a: self.commands.send_notification(
                a.get("title", "JARVIS"), a.get("message", "")
            ),
            "take_screenshot": lambda a: self.commands.take_screenshot(),
            "copy_to_clipboard": lambda a: self.commands.copy_to_clipboard(a.get("text", "")),
            "lock_computer": lambda a: self.commands.lock_computer(),
        }

        handler = dispatch.get(name)
        if handler:
            try:
                return handler(args)
            except Exception as e:
                logger.error(f"Tool error [{name}]: {e}")
                return f"Error executing {name}: {e}"
        return f"Unknown tool: {name}"

    # ── Periodic Status ─────────────────────────────────────────

    def get_status_report(self):
        parts = []
        try:
            cpu = self.commands.get_cpu_usage()
            if cpu:
                parts.append(f"CPU at {cpu}")
        except Exception:
            pass
        try:
            batt = self.commands.get_battery_percent()
            if batt:
                parts.append(f"battery at {batt}")
        except Exception:
            pass
        if parts:
            return "Quick status: " + ", ".join(parts) + ", sir. All systems nominal."
        return "All systems nominal, sir."

    # ── History Management ──────────────────────────────────────

    def clear_history(self):
        self.conversation_history = []
        if self._provider == "gemini":
            self._gemini_chat = None
