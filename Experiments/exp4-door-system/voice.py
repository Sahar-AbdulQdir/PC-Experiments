"""
voice.py - Voice Command Recognition
Listens for: "Arduino open the door" or "Arduino close the door"
"""

import speech_recognition as sr

recognizer = sr.Recognizer()


def listen_for_command(on_command, on_status, get_running):
    """
    Continuously listens for voice commands.
    - on_command(cmd): called with "OPEN" or "CLOSE"
    - on_status(msg): called with status/feedback messages
    - get_running(): returns True while voice mode is active
    """
    with sr.Microphone() as mic:
        on_status("Calibrating microphone...")
        recognizer.adjust_for_ambient_noise(mic, duration=1)
        on_status('Listening... Say "Arduino open the door" or "Arduino close the door"')

        while get_running():
            try:
                audio = recognizer.listen(mic, timeout=5, phrase_time_limit=6)
                text = recognizer.recognize_google(audio).lower()
                on_status(f'Heard: "{text}"')

                # Must contain wake word
                if "arduino" not in text:
                    continue

                if "open" in text:
                    on_command("OPEN")
                elif "close" in text or "shut" in text:
                    on_command("CLOSE")
                else:
                    on_status('Say "open" or "close" after "Arduino"')

            except sr.WaitTimeoutError:
                pass  # No speech heard, keep looping
            except sr.UnknownValueError:
                on_status("Could not understand. Please try again.")
            except sr.RequestError:
                on_status("Speech service error. Check internet connection.")
