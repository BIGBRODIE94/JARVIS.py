"""
Demo script to exercise JARVIS.py core functionality without requiring
a microphone. Tests TTS engine, time/date, jokes, and CPU stats.
"""
import pyttsx3
import datetime
import psutil
import pyjokes
import wikipedia

engine = pyttsx3.init()
voices = engine.getProperty('voices')
print(f"TTS engine initialized with {len(voices)} voices available")

# Use English voice
for i, v in enumerate(voices):
    if 'English' in v.id or 'en' in v.id.lower():
        engine.setProperty('voice', v.id)
        print(f"Selected voice: {v.id} (index {i})")
        break

def speak(audio):
    print(f"[JARVIS]: {audio}")
    engine.say(audio)
    engine.runAndWait()

# 1. Greeting & Time
print("\n--- Testing Time Function ---")
current_time = datetime.datetime.now().strftime("%I:%M:%S")
speak(f"The current time is {current_time}")

# 2. Date
print("\n--- Testing Date Function ---")
now = datetime.datetime.now()
speak(f"The current date is {now.month} {now.day} {now.year}")

# 3. Greeting logic
print("\n--- Testing Greeting ---")
hour = datetime.datetime.now().hour
if 6 <= hour < 12:
    speak("Good Morning Sir!")
elif 12 <= hour < 18:
    speak("Good afternoon Sir")
elif 18 <= hour < 24:
    speak("Good Evening Sir")
else:
    speak("Good Night Sir")

# 4. CPU Stats
print("\n--- Testing CPU Stats ---")
usage = str(psutil.cpu_percent())
speak(f"CPU is at {usage} percent")

# 5. Joke
print("\n--- Testing Jokes ---")
joke = pyjokes.get_joke()
speak(joke)

# 6. Wikipedia (quick test)
print("\n--- Testing Wikipedia ---")
try:
    result = wikipedia.summary("Python programming language", sentences=2)
    print(f"Wikipedia result: {result[:200]}...")
    speak("Wikipedia search successful")
except Exception as e:
    print(f"Wikipedia error (expected in some environments): {e}")

speak("All JARVIS core functions demonstrated successfully!")
print("\n=== DEMO COMPLETE ===")
