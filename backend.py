import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, request, jsonify
from pygame import mixer
import threading
import time
import os
import socket

# --- 1. Set up Logging ---
# We will log everything to a file named 'esp32_events.log'
LOG_FILE = 'esp32_events.log'

# Get the root logger
logger = logging.getLogger()
logger.setLevel(logging.INFO) # Set the minimum level to log

# Create file handler (Rotates log file when it reaches 1MB)
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1024 * 1024, backupCount=5)
file_handler.setLevel(logging.INFO)

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Create a formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add the handlers to the root logger
# (Remove previous handlers if any, to avoid duplicate logs in console)
if logger.hasHandlers():
    logger.handlers.clear()
logger.addHandler(file_handler)
logger.addHandler(console_handler)
# --- End of Logging Setup ---

app = Flask(__name__)

# --- Configuration ---
MP3_FILE_PATH = 'audio.mp3' 
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FULL_MP3_PATH = os.path.join(SCRIPT_DIR, MP3_FILE_PATH)

# Initialize the mixer
try:
    mixer.init(frequency=44100)
except Exception as e:
    logger.error(f"ERROR: Could not initialize pygame mixer. Check audio device. {e}")

# --- Thread for playing sound ---
def play_audio_thread():
    try:
        logger.info(f"Server: Attempting to play MP3: {FULL_MP3_PATH}")
        sound = mixer.Sound(FULL_MP3_PATH)
        sound.play() 
        time.sleep(sound.get_length())
    except Exception as e:
        logger.error(f"Server ERROR: Could not play audio. {e}")

# --- API Endpoint 1: Ping (for STATE_INIT) ---
@app.route('/api/motion_event', methods=['GET'])
def ping_server():
    """Handles the 'ping' from the ESP32 to check if the server is alive."""
    # This will now log to both console and file
    logger.info("Server: Received GET (Ping) request. Responding with OK.")
    return jsonify({"status": "server_is_ready"}), 200

# --- API Endpoint 2: Trigger (for STATE_ACTIVE) ---
@app.route('/api/motion_event', methods=['POST'])
def handle_motion_event():
    """Handles the POST request from the ESP32 to play the sound."""
    try:
        data = request.get_json()
        # This will now log to both console and file
        logger.info(f"Server: Received MOTION POST request. Data: {data}")
    except Exception as e:
        logger.error(f"Server ERROR: Failed to parse MOTION JSON body. {e}")
        return jsonify({"message": "Invalid JSON"}), 400

    audio_thread = threading.Thread(target=play_audio_thread)
    audio_thread.start()
    
    return jsonify({"status": "success", "action": "alert_played"}), 200

# --- API Endpoint 3: Error Logging ---
@app.route('/api/log_error', methods=['POST'])
def handle_error_log():
    """Receives error logs from the ESP32 and logs them."""
    try:
        error_data = request.get_json()
        # This will log as a "WARNING" to stand out in the log file
        logger.warning(f"!! ERROR LOG RECEIVED from {error_data.get('device', 'Unknown')} !! Error: {error_data.get('error', 'No message')}")
    except Exception as e:
        logger.error(f"Server ERROR: Failed to parse log_error JSON. {e}")
    
    return jsonify({"status": "error_logged"}), 200

if __name__ == '__main__':
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)) 
        local_ip = s.getsockname()[0]
        s.close()
    except:
        local_ip = "127.0.0.1 (Check IP Manually)"

    # Use the logger instead of print
    logger.info("=" * 50)
    logger.info("FLASK SERVER IS READY (with File Logging)")
    logger.info("-" * 50)
    logger.info(f"  Your PC's Local IP Address is: {local_ip}")
    logger.info(f"  Motion Endpoint: http://{local_ip}:5000/api/motion_event")
    logger.info(f"  Error Log Endpoint: http://{local_ip}:5000/api/log_error")
    logger.info(f"  Logs are being saved to: {LOG_FILE}")
    logger.info("=" * 50)
    
    app.run(host='192.168.5.212', port=5000)