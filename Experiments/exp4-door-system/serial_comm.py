"""
serial_comm.py - Arduino Serial Communication
Sends OPEN or CLOSE commands to the Arduino over USB.
"""

import serial
import serial.tools.list_ports
import time


def find_arduino():
    """Automatically find the Arduino COM port."""
    for port in serial.tools.list_ports.comports():
        desc = (port.description + port.manufacturer if port.manufacturer else port.description).lower()
        if any(kw in desc for kw in ["arduino", "ch340", "ftdi", "usb serial"]):
            return port.device
    return None


class ArduinoConnection:

    def __init__(self, port=None, baud=9600):
        self.port = port or find_arduino()
        self.baud = baud
        self.connection = None

    def connect(self):
        """Open serial connection to Arduino."""
        if not self.port:
            print("No Arduino found. Check USB connection.")
            return False
        try:
            self.connection = serial.Serial(self.port, self.baud, timeout=1)
            time.sleep(2)  # Wait for Arduino to reset
            print(f"Connected to Arduino on {self.port}")
            return True
        except serial.SerialException as e:
            print(f"Connection failed: {e}")
            return False

    def send(self, command):
        """Send OPEN or CLOSE to Arduino."""
        if not self.connection or not self.connection.is_open:
            print("Not connected to Arduino.")
            return
        self.connection.write((command + "\n").encode())
        print(f"Sent: {command}")

    def disconnect(self):
        """Close the serial connection."""
        if self.connection and self.connection.is_open:
            self.connection.close()
            print("Arduino disconnected.")
