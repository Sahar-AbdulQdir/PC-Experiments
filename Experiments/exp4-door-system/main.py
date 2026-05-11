"""
main.py - Accessible Smart Door System
Main GUI Application

Run: python main.py
"""

import customtkinter as ctk
import threading
from gesture import run_gesture_detection
from voice import listen_for_command
from serial_comm import ArduinoConnection

# App appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Door state
door_state = "CLOSED"

# Arduino connection
arduino = ArduinoConnection()
arduino.connect()

# Mode control flag
mode_running = False


def get_running():
    return mode_running


# ── Door Control ─────────────────────────────────────────────

def open_door(source):
    global door_state
    if door_state == "OPEN":
        set_status("Door is already open!", "orange")
        return
    door_state = "OPEN"
    set_status(f"[{source}] Door Opening...", "green")
    door_label.configure(text="🔓 OPEN", text_color="green")
    arduino.send("OPEN")


def close_door(source):
    global door_state
    if door_state == "CLOSED":
        set_status("Door is already closed!", "orange")
        return
    door_state = "CLOSED"
    set_status(f"[{source}] Door Closing...", "#4FC3F7")
    door_label.configure(text="🔒 CLOSED", text_color="red")
    arduino.send("CLOSE")


def handle_command(cmd, source):
    if cmd == "OPEN":
        open_door(source)
    elif cmd == "CLOSE":
        close_door(source)


# ── Status Helper ────────────────────────────────────────────

def set_status(message, color="white"):
    status_label.configure(text=message, text_color=color)
    log_box.configure(state="normal")
    log_box.insert("end", message + "\n")
    log_box.see("end")
    log_box.configure(state="disabled")


# ── Mode Buttons ─────────────────────────────────────────────

def start_gesture():
    global mode_running
    stop_modes()
    mode_running = True
    set_status("Gesture Mode active — show hand to camera", "lightgreen")

    def gesture_thread():
        run_gesture_detection(
            on_command=lambda cmd: handle_command(cmd, "GESTURE"),
            get_running=get_running
        )
    threading.Thread(target=gesture_thread, daemon=True).start()


def start_voice():
    global mode_running
    stop_modes()
    mode_running = True
    set_status("Voice Mode active — speak your command", "#4FC3F7")

    def voice_thread():
        listen_for_command(
            on_command=lambda cmd: handle_command(cmd, "VOICE"),
            on_status=lambda msg: set_status(msg),
            get_running=get_running
        )
    threading.Thread(target=voice_thread, daemon=True).start()


def stop_modes():
    global mode_running
    mode_running = False
    set_status("Stopped. Choose a mode to begin.", "gray")


def exit_app():
    stop_modes()
    arduino.disconnect()
    app.destroy()


def show_info():
    popup = ctk.CTkToplevel(app)
    popup.title("How to Use")
    popup.geometry("400x300")
    popup.grab_set()

    info = (
        "GESTURE MODE\n"
        "  ✋ Open Hand  → Open door\n"
        "  ✊ Closed Fist → Close door\n"
        "  Hold gesture for ~1.5 seconds.\n\n"
        "VOICE MODE\n"
        '  Say "Arduino open the door"\n'
        '  Say "Arduino close the door"\n'
        '  Must say "Arduino" first.\n\n'
        "BUTTONS\n"
        "  Stop/Reset clears the current mode."
    )
    ctk.CTkLabel(popup, text=info, font=("Consolas", 13),
                 justify="left").pack(padx=20, pady=20)
    ctk.CTkButton(popup, text="Close", command=popup.destroy).pack(pady=10)


# ── Build GUI ────────────────────────────────────────────────

app = ctk.CTk()
app.title("Accessible Smart Door System")
app.geometry("600x560")
app.protocol("WM_DELETE_WINDOW", exit_app)

# Title
ctk.CTkLabel(app, text="Accessible Smart Door System",
             font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(20, 4))
ctk.CTkLabel(app, text="Gesture + Voice Control",
             font=ctk.CTkFont(size=13), text_color="gray").pack()

# Door state display
door_label = ctk.CTkLabel(app, text="🔒 CLOSED",
                          font=ctk.CTkFont(size=32, weight="bold"),
                          text_color="red")
door_label.pack(pady=16)

# Status label
status_label = ctk.CTkLabel(app, text="Waiting for input...",
                             font=ctk.CTkFont(size=13))
status_label.pack()

# Buttons
btn_frame = ctk.CTkFrame(app, fg_color="transparent")
btn_frame.pack(pady=16)

ctk.CTkButton(btn_frame, text="🖐  Start Gesture Mode",
              width=180, height=44, fg_color="#238636",
              command=start_gesture).grid(row=0, column=0, padx=8, pady=6)

ctk.CTkButton(btn_frame, text="🎙  Start Voice Mode",
              width=180, height=44, fg_color="#1F6FEB",
              command=start_voice).grid(row=0, column=1, padx=8, pady=6)

ctk.CTkButton(btn_frame, text="⏹  Stop / Reset",
              width=180, height=44, fg_color="#DA3633",
              command=stop_modes).grid(row=1, column=0, padx=8, pady=6)

ctk.CTkButton(btn_frame, text="ℹ  Info",
              width=80, height=44, fg_color="#30363D",
              command=show_info).grid(row=1, column=1, padx=(8, 0), pady=6, sticky="w")

ctk.CTkButton(btn_frame, text="✕  Exit",
              width=90, height=44, fg_color="#30363D",
              command=exit_app).grid(row=1, column=1, padx=(0, 8), pady=6, sticky="e")

# Activity log
ctk.CTkLabel(app, text="Activity Log", font=ctk.CTkFont(size=12),
             text_color="gray").pack()

log_box = ctk.CTkTextbox(app, height=140, font=("Consolas", 11),
                          state="disabled")
log_box.pack(padx=20, pady=(4, 20), fill="x")

# Run app
app.mainloop()
