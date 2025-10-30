import argparse
import json
import sys
import time
import subprocess
from pathlib import Path

import serial  # pip install pyserial
from serial.tools import list_ports

CONFIG_FILE = "esp_config.json"
DEFAULT_BAUD = 115200


def nudge_board(port, baud=DEFAULT_BAUD):
    """Try to stop any running script and leave the board ready for REPL."""
    try:
        with serial.Serial(port, baudrate=baud, timeout=0.4) as ser:
            ser.dtr = False
            ser.rts = True
            time.sleep(0.05)
            ser.dtr = False
            ser.rts = False
            time.sleep(0.2)
            ser.write(b'\r\x03\x03')  # Ctrl-C twice
            ser.flush()
            time.sleep(0.2)
            ser.write(b'\x04')  # Ctrl-D soft reset
            ser.flush()
            time.sleep(0.2)
    except Exception as e:
        print(f"⚠️ Nudge failed ({e}), continuing...")


def run(cmd):
    print("→", " ".join(cmd))
    return subprocess.run(cmd, capture_output=True, text=True)


def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def upload_files(port, files):
    for f in files:
        if not Path(f).exists():
            print(f"⚠️ File not found: {f}")
            continue
        for attempt in range(1, 4):
            res = run(["mpremote", "connect", port, "cp", f, ":"])
            if res.returncode == 0:
                if res.stdout.strip():
                    print(res.stdout.strip())
                break
            print(f"❌ cp failed for {f} (try {attempt}/3)")
            if res.stdout:
                print(res.stdout)
            if res.stderr:
                print(res.stderr)
            nudge_board(port)
            time.sleep(0.4)
        else:
            sys.exit(1)


def pull_file(port, remote):
    local = Path(remote).name
    nudge_board(port)
    res = run(["mpremote", "connect", port, "cp", f":{remote}", local])
    if res.returncode != 0:
        print("❌ pull failed")
        if res.stdout:
            print(res.stdout)
        if res.stderr:
            print(res.stderr)
        sys.exit(1)
    if res.stdout.strip():
        print(res.stdout.strip())
    print(f"✅ Pulled {remote} -> {local}")


def delete_file(port, remote):
    nudge_board(port)
    res = run(["mpremote", "connect", port, "rm", remote])
    if res.returncode != 0:
        print("❌ delete failed")
        if res.stdout:
            print(res.stdout)
        if res.stderr:
            print(res.stderr)
        sys.exit(1)
    if res.stdout.strip():
        print(res.stdout.strip())
    print(f"🗑️ Deleted {remote}")


def list_files(port, folder=None):
    """List files/folders on the device."""
    nudge_board(port)
    args = ["mpremote", "connect", port, "ls"]
    if folder:
        args.append(folder)
    res = run(args)
    if res.returncode != 0:
        print("❌ ls failed")
        if res.stdout:
            print(res.stdout)
        if res.stderr:
            print(res.stderr)
        sys.exit(1)
    print(res.stdout or "(empty)")


def main():
    parser = argparse.ArgumentParser(description="ESP32 push/pull helper using mpremote")
    parser.add_argument("--run", action="store_true", help="Run entry point after upload")
    parser.add_argument("--pull", metavar="REMOTE_FILE", help="Pull a file from ESP32 to local")
    parser.add_argument("--delete", metavar="REMOTE_FILE", help="Delete a file on ESP32")
    parser.add_argument("--ls", nargs="?", const="", metavar="REMOTE_DIR", help="List files on ESP32 (root or folder)")
    args = parser.parse_args()

    cfg = load_config()
    port = cfg.get("port", "COM6")
    files = cfg.get("files", [])
    entry = cfg.get("entry_point", "main.py")

    # Handle single actions first
    if args.pull:
        pull_file(port, args.pull)
        return
    if args.delete:
        delete_file(port, args.delete)
        return
    if args.ls is not None:
        list_files(port, args.ls)
        return

    # Default: upload (and optionally run)
    print(f"📦 Using port: {port}")
    print(f"📁 Files to upload: {', '.join(files) if files else '(none)'}")
    print(f"🚀 Entry point: {entry}")
    print(f"⚙️ Run after upload: {'Yes' if args.run else 'No'}\n")

    nudge_board(port)
    upload_files(port, files)

    if args.run:
        nudge_board(port)
        res = run(["mpremote", "connect", port, "run", entry])
        if res.returncode != 0:
            print("❌ run failed")
            if res.stdout:
                print(res.stdout)
            if res.stderr:
                print(res.stderr)
            sys.exit(1)
        if res.stdout.strip():
            print(res.stdout.strip())


if __name__ == "__main__":
    main()
