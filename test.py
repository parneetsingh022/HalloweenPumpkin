# type: ignore
"""
wifi_setup.py
Loads Wi-Fi credentials from .env and connects using wifi_connector.
"""

import os
from wifi_connector import connect_wifi

def load_env():
    """Simple .env loader for MicroPython."""
    print("LOAD START")
    creds = {}
    try:
        with open(".env") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    creds[key.strip()] = value.strip()
    except Exception as e:
        print(f"Could not read .env file: {e}")

    print("LOAD END")
    return creds


def connect_from_env(led_pin=None):
    """Connect to Wi-Fi using credentials from .env"""
    env = load_env()
    ssid = env.get("ssid")
    password = env.get("password")


    if not ssid or not password:
        print("Missing WIFI_SSID or WIFI_PASS in .env")
        return False, None, None

    print(f"Connecting to Wi-Fi ({ssid}) from .env ...")
    ok, wlan, ip = connect_wifi(ssid=ssid, password=password, led_pin=led_pin)
    if ok:
        print(f"Connected to {ssid} at {ip}")
    else:
        print("Wi-Fi connection failed.")

    return ok, wlan, ip


# Allow standalone test run
if __name__ == "__main__":
    connect_from_env()
