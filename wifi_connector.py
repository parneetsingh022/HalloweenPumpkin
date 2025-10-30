# Minimal, robust Wi-Fi helper for MicroPython (ESP32)
# Save as: wifi_connector.py

# type: ignore
import time
import network

try:
    from machine import Pin
except ImportError:
    Pin = None  # allows importing on host without machine module

# Optional: if you keep WIFI_SSID/WIFI_PASS in wifi_config.py
def _load_creds(ssid, password):
    if ssid and password:
        return ssid, password
    try:
        import wifi_config  # must provide WIFI_SSID, WIFI_PASS
        return ssid or getattr(wifi_config, "WIFI_SSID"), password or getattr(wifi_config, "WIFI_PASS")
    except Exception:
        return ssid, password


class WiFiManager:
    """
    Usage:
        from wifi_connector import WiFiManager
        wifi = WiFiManager(ssid="MyWiFi", password="mypassword", led_pin=5)
        ok = wifi.ensure()   # returns True/False
        wlan = wifi.wlan     # access the underlying WLAN object
        ip = wifi.ip()       # string or None
    """
    def __init__(self, ssid=None, password=None, *, led_pin=None, timeout_s=15, retries=3, backoff_s=2, ifconfig=None, verbose=True):
        """
        ssid/password: Wi-Fi credentials. If None, tries to import from wifi_config.py
        led_pin: optional GPIO to blink during connect (e.g., 5)
        timeout_s: per-attempt timeout
        retries: number of attempts before giving up
        backoff_s: seconds to wait between attempts (exponential backoff applied)
        ifconfig: optional tuple (ip, mask, gw, dns) for static IP
        """
        self.ssid, self.password = _load_creds(ssid, password)
        self.wlan = network.WLAN(network.STA_IF)
        self.timeout_s = max(1, int(timeout_s))
        self.retries = max(1, int(retries))
        self.backoff_s = max(0, int(backoff_s))
        self.ifconfig_cfg = ifconfig
        self.verbose = verbose

        self.led = None
        if led_pin is not None and Pin is not None:
            try:
                self.led = Pin(led_pin, Pin.OUT)
                self.led.value(0)
            except Exception:
                self.led = None

    # ---------- public API ----------

    def ensure(self):
        """Ensure Wi-Fi is connected. Returns True/False."""
        if self.is_connected():
            if self.verbose:
                print("Wi-Fi already connected:", self.ip())
            return True
        return self._connect_with_retries()

    def disconnect(self):
        """Disconnect and deactivate Wi-Fi."""
        try:
            self.wlan.disconnect()
        except Exception:
            pass
        self.wlan.active(False)
        if self.led:
            self.led.value(0)

    def is_connected(self):
        try:
            return self.wlan.active() and self.wlan.isconnected()
        except Exception:
            return False

    def ip(self):
        try:
            return self.wlan.ifconfig()[0] if self.is_connected() else None
        except Exception:
            return None

    # ---------- internals ----------

    def _blink(self, on_ms=120, off_ms=120):
        if not self.led:
            time.sleep_ms(off_ms)
            return
        self.led.value(1)
        time.sleep_ms(on_ms)
        self.led.value(0)
        time.sleep_ms(off_ms)

    def _prepare(self):
        self.wlan.active(True)
        # Optional static IP
        if self.ifconfig_cfg and isinstance(self.ifconfig_cfg, (tuple, list)) and len(self.ifconfig_cfg) == 4:
            try:
                self.wlan.ifconfig(tuple(self.ifconfig_cfg))
                if self.verbose:
                    print("Using static IP:", self.ifconfig_cfg)
            except Exception as e:
                if self.verbose:
                    print("Failed to set static IP:", e)

    def _wait_for_ip(self, timeout_s):
        start = time.ticks_ms()
        last_dot = 0
        while not self.wlan.isconnected():
            # Show progress and blink
            if self.verbose:
                now = time.ticks_ms()
                if time.ticks_diff(now, last_dot) > 500:
                    print(".", end="")
                    last_dot = now
            self._blink(80, 120)
            if time.ticks_diff(time.ticks_ms(), start) > timeout_s * 1000:
                return False
        if self.verbose:
            print()
        return True

    def _connect_once(self):
        if not self.ssid or not self.password:
            if self.verbose:
                print("Wi-Fi credentials missing. Provide ssid/password or wifi_config.py")
            return False

        if self.verbose:
            print('Connecting to Wi-Fi:', self.ssid)
        self._prepare()

        try:
            # If already trying, disconnect first
            if self.wlan.isconnected():
                return True
            try:
                self.wlan.disconnect()
            except Exception:
                pass
            self.wlan.connect(self.ssid, self.password)
        except Exception as e:
            if self.verbose:
                print("Connect call failed:", e)
            return False

        ok = self._wait_for_ip(self.timeout_s)
        if ok:
            ip = self.ip()
            if self.verbose:
                print("Wi-Fi Connected:", ip)
            if self.led:
                # quick success blink
                for _ in range(2):
                    self._blink(50, 50)
            return True

        if self.verbose:
            print("\nWi-Fi connection timeout.")
        try:
            self.wlan.disconnect()
        except Exception:
            pass
        return False

    def _connect_with_retries(self):
        delay = self.backoff_s
        for attempt in range(1, self.retries + 1):
            if self.verbose:
                print("Attempt", attempt, "of", self.retries)
            if self._connect_once():
                return True
            if attempt < self.retries and delay > 0:
                if self.verbose:
                    print("Retrying in", delay, "s...")
                # gentle blink during backoff
                t_end = time.ticks_add(time.ticks_ms(), delay * 1000)
                while time.ticks_diff(t_end, time.ticks_ms()) > 0:
                    self._blink(30, 120)
                delay = min(delay * 2, 30)  # cap backoff
        if self.verbose:
            print("Wi-Fi connection failed after retries.")
        return False


# -------- One-liner helper if you prefer functions over classes --------

def connect_wifi(ssid=None, password=None, *, timeout_s=15, retries=3, backoff_s=2, led_pin=None, ifconfig=None, verbose=True):
    """
    Functional wrapper. Returns (ok: bool, wlan: network.WLAN, ip: str|None)
    """
    manager = WiFiManager(
        ssid=ssid,
        password=password,
        led_pin=led_pin,
        timeout_s=timeout_s,
        retries=retries,
        backoff_s=backoff_s,
        ifconfig=ifconfig,
        verbose=verbose,
    )
    ok = manager.ensure()
    return ok, manager.wlan, manager.ip()
