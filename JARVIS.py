import pyttsx3  # pip install pyttsx3
import datetime
import speech_recognition as sr  # pip install Speech Recognition
import wikipedia  # pip install wikipedia
import smtplib
import webbrowser
import os
import pyautogui  # pip install pyautogui
import psutil
import pyjokes
import pyaudio
import sys

engine = pyttsx3.init()
voices = engine.getProperty('voices')
print(voices[7].id)
engine.setProperty('voice', voices[7].id)
engine.say("Hello Sir!")
engine.runAndWait()


def speak(audio):
    engine.say(audio)
    engine.runAndWait()


def time():
    # engine.say("current time is")
    Time = datetime.datetime.now().strftime("%I:%M:%S")
    speak("the current time is")
    speak(Time)


def date():
    # engine.say("Today\'s date is")
    year = str(datetime.datetime.now().year)
    month = str(datetime.datetime.now().month)
    calender = str(datetime.datetime.now().day)
    speak("the current date is")
    speak(month)
    speak(calender)
    speak(year)


def wishMe():
    speak("Welcome back! Hope you are doing well")
    # speak("the current time is")
    time()
    # speak("the current date is")
    date()
    hour: int = datetime.datetime.now().hour
    if 6 <= hour < 12:
        speak("Good Morning Sir!")
    elif 12 <= hour < 18:
        speak("Good afternoon Sir")
    elif 18 <= hour < 24:
        speak("Good Evening Sir")
    else:
        speak("Good Night Sir")

    speak("Please tell me how may i help you today?")


def takeCommand():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening....")
        r.pause_threshold = 1
        audio = r.listen(source)
    try:
        print("Recognizing....")
        query = r.recognize_google(audio)
        print(query)

    except Exception as e:
        print(e)

        return "None"
    return query


# All the commands starts from here
def sendEmail(to, content):
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.ehlo()
    server.starttls()
    server.login('affanc666@gmail.com', 'dubkix-fitqId-2jyfbu')
    server.sendmail('aac140930@utdallas.edu', to, content)
    server.close()


def screenshot():
    img = pyautogui.screenshot()
    img.save('/Users/affanchowdhury/Downloads/')


def cpu():
    usage = str(psutil.cpu_percent())
    speak('CPU is at' + usage)
    battery = str(psutil.battery_percent())
    speak('Battery is at' + battery)


def jokes():
    speak(pyjokes.get_joke())


if __name__ == '__main__':
    wishMe()
    while True:
        query = takeCommand().lower()
        if 'time' in query:
            time()

        elif 'date' in query:
            date()

        elif 'wikipedia' in query.lower():
            speak("Searching...")
            query = query.replace("wikipedia", "")
            result = wikipedia.summary(query, sentences=5)
            print(result)
            speak(result)

        elif 'send email to myself' in query.lower():
            try:
                speak("What is the message i should say?")
                content = takeCommand()
                to = 'aac140930@utdallas.edu'
                sendEmail(to, content)
                # speak("Email Sent")
                speak("Email has been sent successfully")
            except Exception as e:
                print(e)
                speak("Unable to send email")

            # elif 'search in chrome' in query:
            # speak("What should i search?")
            # path = "/Applications/Google\ Chrome.app/Contents/MacOS/Google Chrome"
            # search = takeCommand().lower()
            # webbrowser.get(path).open_new_tab(search + '.com')

        elif 'search in chrome' in query.lower():
            speak("What should i open")
            search = takeCommand().lower()
            websites = takeCommand()
            # webbrowser.open('http://www.python.org')
            # speak("opening websites in chrome" + websites)
            # chrome = open('websites.txt')
            # chrome.close()
            webbrowser.get(websites)
            # new = 2
            # webbrowser.get(using='google-chrome').open(url, new=new)
        elif 'open chrome' in query.lower():
            os.chdir('/Applications/Google Chrome.app')
            webbrowser.open(os.chdir())
        elif 'open google' in query.lower():
            webbrowser.open('google.com')
        elif 'open stackoverflow' in query.lower():
            webbrowser.open("stackoverflow.com")
        elif 'log out' in query:
            os.system("shutdown /l /t 06")
            speak("Logging off your system boss")
            speak("Bye Sir, Have a good day")
        elif 'shutdown' in query:
            os.system("shutdown /s /t 1")
        elif 'restart' in query:
            os.system("shutdown /r /t 1")
        elif 'play music' in query:
            os.chdir = '/Users/affanchowdhury/Downloads'
            songs = os.listdir(songs)
            for music in songs:
                if songs.endswith('.mp3'):
                    os.chdir(os.path.join(os.chdir[3]))
        elif 'remember that' in query:
            speak("What should i remember")
            data = takeCommand()
            speak("You said me to remember that" + data)
            remember = open('data.txt', 'w')
            remember.write(data)
            remember.close()
        elif 'screenshot' in query:
            screenshot()
            speak("Done!")
        elif 'cpu' in query:
            cpu()
        elif 'joke' in query:
            jokes()
        elif 'offline' in query:
            quit()
        elif 'quit' in query:
            speak("quitting Boss")
            break
        elif 'exit' in query:
            exit()
            speak("Goodbye Boss")
