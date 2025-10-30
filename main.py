# type: ignore

import time
import network
import urequests
from machine import Pin, Timer

# --- Configuration ---
WIFI_SSID = "ATT4NET_TMP"
WIFI_PASS = "12345678@1"
# Use your PC's IP
BASE_IP = "http://192.168.5.187:5000" 
API_MOTION_ENDPOINT = BASE_IP + "/api/motion_event"
API_LOG_ENDPOINT = BASE_IP + "/api/log_error"  # NEW: Error logging endpoint

MOTION_PIN = 21     # D21 -> GPIO 21
LED_PIN = 5         # D5  -> GPIO 5
LED_FLASH_TIME_MS = 8000  # Flash LED for 8 seconds
TOTAL_COOLDOWN_MS = 10000 # Total cooldown is 10 seconds

# --- State Definitions ---
STATE_INIT = 0
STATE_IDLE = 1
STATE_ACTIVE = 2

# --- Global Variables ---
current_state = STATE_INIT
led = Pin(LED_PIN, Pin.OUT)
pir = Pin(MOTION_PIN, Pin.IN, Pin.PULL_DOWN)
wlan = network.WLAN(network.STA_IF) # Define wlan globally

cooldown_timer = Timer(0) 
led_stop_timer = Timer(1) 
led_flash_timer = Timer(2) 


# --- Helper Functions ---

def blink_led(count=3, speed_ms=100):
    led.value(0)
    for _ in range(count):
        led.value(1)
        time.sleep_ms(speed_ms)
        led.value(0)
        time.sleep_ms(speed_ms)

def connect_wifi():
    global wlan
    wlan.active(True)
    if wlan.isconnected():
        print("Wi-Fi already connected.")
        return True
        
    print('Connecting to Wi-Fi...')
    wlan.connect(WIFI_SSID, WIFI_PASS)
    
    timeout = 15
    while not wlan.isconnected() and timeout > 0:
        time.sleep(1)
        timeout -= 1
        print('.', end='')
        
    if wlan.isconnected():
        print('\nWi-Fi Connected:', wlan.ifconfig()[0])
        return True
    else:
        print('\nWi-Fi connection failed!')
        wlan.active(False)
        return False

# --- NEW: Error Logging Function ---
def log_error_to_web(error_message):
    """Sends a POST request to the error logging endpoint."""
    global wlan
    if not wlan.isconnected():
        print(f"Cannot log error, Wi-Fi is down. Error: {error_message}")
        return

    print(f"Logging error to web: {error_message}")
    try:
        data = {
            "device": "ESP32_Motion_Sensor",
            "error": str(error_message)
        }
        response = urequests.post(API_LOG_ENDPOINT, json=data)
        if response.status_code == 200:
            print("Error log successful.")
        else:
            print(f"Failed to log error, server returned HTTP {response.status_code}")
        response.close()
    except Exception as e:
        print(f"Exception while logging error: {e}")

# --- UPDATED: API Ping Function ---
def ping_api():
    print(f"Pinging API: {API_MOTION_ENDPOINT}")
    try:
        response = urequests.get(API_MOTION_ENDPOINT, timeout=5) 
        if response.status_code == 200:
            print("API Ping Success: Server is ready.")
            response.close()
            return True
        else:
            error_msg = f"API Ping Failed: Server returned HTTP {response.status_code}"
            print(error_msg)
            response.close()
            # We can log this error because Wi-Fi is working
            log_error_to_web(error_msg) # MODIFIED: Log this error
            return False
    except Exception as e:
        error_msg = f"API Ping Failed: {e}"
        print(error_msg)
        log_error_to_web(error_msg) # MODIFIED: Log this error
        return False

# --- UPDATED: API Post Function ---
def call_api_post():
    print(f"Calling API (POST) to play sound...")
    try:
        data = {"device": "ESP32", "event": "motion_detected"}
        response = urequests.post(API_MOTION_ENDPOINT, json=data)
        if response.status_code == 200: 
            print("API POST Success: HTTP 200")
        else:
            error_msg = f"API POST Failed: HTTP {response.status_code}"
            print(error_msg)
            log_error_to_web(error_msg) # MODIFIED: Log this error
        response.close()
    except Exception as e:
        error_msg = f"API POST Failed: {e}"
        print(error_msg)
        log_error_to_web(error_msg) # MODIFIED: Log this error

# --- Timer Callback Functions ---

def toggle_led_callback(t):
    led.value(not led.value()) 

def stop_flashing_callback(t):
    print("8s timer finished. Stopping LED flash.")
    led_flash_timer.deinit() 
    led.value(0)             

def set_state_idle_callback(t):
    global current_state
    print("10s cooldown finished. -> STATE_IDLE")
    current_state = STATE_IDLE


# --- Main State Machine Logic ---
# (No changes needed in the main loop logic, only in the functions it calls)
def state_machine_logic():
    global current_state

    # --- STATE 0: INITIALIZATION ---
    if current_state == STATE_INIT:
        print("STATE_INIT: Checking services...")
        # 1. Check Wi-Fi
        if not connect_wifi():
            blink_led(1, 1000) # One long blink for Wi-Fi error (cannot log this)
            time.sleep(5)      
            return 
            
        # 2. Check API
        if not ping_api():
            blink_led(2, 500)  # Two blinks for API error (this IS logged)
            time.sleep(5)      
            return 
        
        # 3. Success!
        print("STATE_INIT: Setup complete!")
        blink_led(3, 100) 
        print("Transitioning to -> STATE_IDLE")
        led.value(0) 
        current_state = STATE_IDLE

    # --- STATE 1: IDLE (Waiting for motion) ---
    elif current_state == STATE_IDLE:
        if pir.value() == 1:
            print("Motion Detected! -> STATE_ACTIVE")
            
            call_api_post()
            led_flash_timer.init(period=200, mode=Timer.PERIODIC, callback=toggle_led_callback)
            led_stop_timer.init(period=LED_FLASH_TIME_MS, mode=Timer.ONE_SHOT, callback=stop_flashing_callback)
            cooldown_timer.init(period=TOTAL_COOLDOWN_MS, mode=Timer.ONE_SHOT, callback=set_state_idle_callback)
            current_state = STATE_ACTIVE

    # --- STATE 2: ACTIVE (Cooldown period) ---
    elif current_state == STATE_ACTIVE:
        pass


# --- Main Application Start ---

print("Starting State Machine...")
while True:
    state_machine_logic()
    time.sleep_ms(50)
