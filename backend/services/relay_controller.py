"""
backend/services/relay_controller.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Production relay controller with multiple hardware backend support.

Backends:
  - HTTPRelayController   → sends commands to an HTTP-based relay controller
  - USBRelayController    → sends commands via USB serial (CH340, FTDI, etc.)
  - GPIORelayController   → controls GPIO pins (Raspberry Pi / Jetson Nano)
  - SimulatedRelayController → logs only (for development/testing)

All backends share a common interface:
  - open_gate(gate_id: str) → dict
  - close_gate(gate_id: str) → dict

Safety features:
  - Anti-rapid-trigger cooldown per gate
  - Thread-safe gate access (one operation at a time per gate)
  - Configurable hold-open duration
  - Full event logging
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from typing import Dict, Optional

import httpx

from backend.config import settings

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base Class
# ---------------------------------------------------------------------------

class RelayController(ABC):
    """
    Abstract base for relay/gate controllers.

    Subclasses implement ``_activate(gate_id)`` and ``_deactivate(gate_id)``
    for the actual hardware interaction.  The base class handles:
      - Thread-safe locking per gate
      - Anti-rapid-trigger cooldown
      - Timed auto-close
      - Logging
    """

    def __init__(self):
        self._gate_locks: Dict[str, threading.Lock] = {}
        self._last_trigger: Dict[str, float] = {}

    def _get_lock(self, gate_id: str) -> threading.Lock:
        if gate_id not in self._gate_locks:
            self._gate_locks[gate_id] = threading.Lock()
        return self._gate_locks[gate_id]

    def open_gate(self, gate_id: str) -> dict:
        """
        Open a gate with cooldown protection and auto-close.

        Returns a dict with status, gate, and timing info.
        """
        lock = self._get_lock(gate_id)

        if not lock.acquire(blocking=False):
            log.warning("Gate '%s' is already being operated — skipping", gate_id)
            return {"status": "busy", "gate": gate_id, "message": "Gate operation already in progress"}

        try:
            # Anti-rapid-trigger check
            now = time.time()
            last = self._last_trigger.get(gate_id, 0)
            elapsed = now - last

            if elapsed < settings.GATE_COOLDOWN_SECONDS:
                remaining = round(settings.GATE_COOLDOWN_SECONDS - elapsed, 1)
                log.info(
                    "Gate '%s' cooldown active — %.1fs remaining",
                    gate_id, remaining,
                )
                return {
                    "status": "cooldown",
                    "gate": gate_id,
                    "message": f"Gate triggered too recently. Wait {remaining}s.",
                    "cooldown_remaining": remaining,
                }

            self._last_trigger[gate_id] = now

            # Activate relay
            log.info("GATE OPEN → %s (hold for %ds)", gate_id, settings.GATE_OPEN_DURATION)
            result = self._activate(gate_id)

            # Schedule auto-close in a daemon thread
            threading.Thread(
                target=self._auto_close,
                args=(gate_id,),
                daemon=True,
                name=f"gate-close-{gate_id}",
            ).start()

            return {
                "status": "opened",
                "gate": gate_id,
                "hold_duration": settings.GATE_OPEN_DURATION,
                **result,
            }

        except Exception as e:
            log.error("Gate '%s' open failed: %s", gate_id, e)
            return {"status": "error", "gate": gate_id, "message": str(e)}

        finally:
            lock.release()

    def close_gate(self, gate_id: str) -> dict:
        """Manually close a gate."""
        try:
            log.info("GATE CLOSE → %s", gate_id)
            result = self._deactivate(gate_id)
            return {"status": "closed", "gate": gate_id, **result}
        except Exception as e:
            log.error("Gate '%s' close failed: %s", gate_id, e)
            return {"status": "error", "gate": gate_id, "message": str(e)}

    def _auto_close(self, gate_id: str):
        """Wait for hold duration, then close the gate."""
        time.sleep(settings.GATE_OPEN_DURATION)
        try:
            self._deactivate(gate_id)
            log.info("GATE AUTO-CLOSE → %s (after %ds)", gate_id, settings.GATE_OPEN_DURATION)
        except Exception as e:
            log.error("Gate '%s' auto-close failed: %s", gate_id, e)

    @abstractmethod
    def _activate(self, gate_id: str) -> dict:
        """Hardware-specific: energize the relay to open the gate."""
        ...

    @abstractmethod
    def _deactivate(self, gate_id: str) -> dict:
        """Hardware-specific: de-energize the relay to close the gate."""
        ...


# ---------------------------------------------------------------------------
# HTTP Relay Controller (existing behavior — sends HTTP commands)
# ---------------------------------------------------------------------------

class HTTPRelayController(RelayController):
    """Sends open/close commands to an HTTP-based relay controller."""

    def __init__(self, base_url: str = ""):
        super().__init__()
        self.base_url = (base_url or settings.GATE_API_URL).rstrip("/")

    def _activate(self, gate_id: str) -> dict:
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.post(
                    f"{self.base_url}/open",
                    json={"gate": gate_id},
                )
                resp.raise_for_status()
                return {"method": "http", "response": resp.json()}
        except Exception as e:
            log.warning("HTTP relay unreachable — gate '%s' command simulated. Error: %s", gate_id, e)
            return {"method": "http_simulated", "note": str(e)}

    def _deactivate(self, gate_id: str) -> dict:
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.post(
                    f"{self.base_url}/close",
                    json={"gate": gate_id},
                )
                resp.raise_for_status()
                return {"method": "http", "response": resp.json()}
        except Exception as e:
            log.debug("HTTP relay close — gate '%s' simulated. Error: %s", gate_id, e)
            return {"method": "http_simulated", "note": str(e)}


# ---------------------------------------------------------------------------
# USB Serial Relay Controller
# ---------------------------------------------------------------------------

class USBRelayController(RelayController):
    """
    Controls USB serial relay boards (CH340, FTDI, HID).

    Common relay board protocol:
      - Send 0xA0 0x01 0x01 0xA2 to turn relay 1 ON
      - Send 0xA0 0x01 0x00 0xA1 to turn relay 1 OFF

    The port and protocol should be configured per your hardware.
    """

    # Gate ID → relay channel mapping
    GATE_CHANNEL_MAP = {
        "entry": 1,
        "exit": 2,
    }

    def __init__(self, port: str = ""):
        super().__init__()
        self.port = port or settings.RELAY_PORT
        self._serial = None

    def _get_serial(self):
        """Lazy-initialize serial connection."""
        if self._serial is None or not self._serial.is_open:
            try:
                import serial
                self._serial = serial.Serial(
                    port=self.port,
                    baudrate=9600,
                    timeout=1,
                )
                log.info("USB relay connected on %s", self.port)
            except ImportError:
                raise RuntimeError(
                    "pyserial is required for USB relay control. "
                    "Install with: pip install pyserial"
                )
            except Exception as e:
                raise RuntimeError(f"Failed to open serial port {self.port}: {e}")
        return self._serial

    def _activate(self, gate_id: str) -> dict:
        channel = self.GATE_CHANNEL_MAP.get(gate_id, 1)
        ser = self._get_serial()
        # Common relay board ON command
        cmd = bytes([0xA0, channel, 0x01, 0xA0 + channel + 0x01])
        ser.write(cmd)
        log.info("USB relay: channel %d ON (gate=%s)", channel, gate_id)
        return {"method": "usb_serial", "channel": channel, "port": self.port}

    def _deactivate(self, gate_id: str) -> dict:
        channel = self.GATE_CHANNEL_MAP.get(gate_id, 1)
        ser = self._get_serial()
        # Common relay board OFF command
        cmd = bytes([0xA0, channel, 0x00, 0xA0 + channel])
        ser.write(cmd)
        log.info("USB relay: channel %d OFF (gate=%s)", channel, gate_id)
        return {"method": "usb_serial", "channel": channel, "port": self.port}


# ---------------------------------------------------------------------------
# GPIO Relay Controller (Raspberry Pi / Jetson)
# ---------------------------------------------------------------------------

class GPIORelayController(RelayController):
    """
    Controls GPIO-connected relay modules.

    Gate ID → GPIO pin mapping (configurable).
    Default: entry=17, exit=27 (BCM numbering).
    """

    GATE_PIN_MAP = {
        "entry": 17,
        "exit": 27,
    }

    def __init__(self):
        super().__init__()
        self._gpio = None

    def _init_gpio(self):
        if self._gpio is None:
            try:
                import RPi.GPIO as GPIO
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                for pin in self.GATE_PIN_MAP.values():
                    GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
                self._gpio = GPIO
                log.info("GPIO relay initialized — pins: %s", self.GATE_PIN_MAP)
            except ImportError:
                raise RuntimeError(
                    "RPi.GPIO is required for GPIO relay control. "
                    "Install with: pip install RPi.GPIO"
                )

    def _activate(self, gate_id: str) -> dict:
        self._init_gpio()
        pin = self.GATE_PIN_MAP.get(gate_id, 17)
        self._gpio.output(pin, self._gpio.HIGH)
        log.info("GPIO relay: pin %d HIGH (gate=%s)", pin, gate_id)
        return {"method": "gpio", "pin": pin}

    def _deactivate(self, gate_id: str) -> dict:
        self._init_gpio()
        pin = self.GATE_PIN_MAP.get(gate_id, 17)
        self._gpio.output(pin, self._gpio.LOW)
        log.info("GPIO relay: pin %d LOW (gate=%s)", pin, gate_id)
        return {"method": "gpio", "pin": pin}


# ---------------------------------------------------------------------------
# Simulated Relay Controller (for development/testing)
# ---------------------------------------------------------------------------

class SimulatedRelayController(RelayController):
    """Logs gate commands without controlling any hardware."""

    def _activate(self, gate_id: str) -> dict:
        log.info("SIMULATED: gate '%s' opened", gate_id)
        return {"method": "simulated"}

    def _deactivate(self, gate_id: str) -> dict:
        log.info("SIMULATED: gate '%s' closed", gate_id)
        return {"method": "simulated"}


# ---------------------------------------------------------------------------
# Factory — instantiate the correct controller based on RELAY_TYPE config
# ---------------------------------------------------------------------------

_controller_instance: Optional[RelayController] = None
_controller_lock = threading.Lock()


def get_relay_controller() -> RelayController:
    """Return the singleton relay controller based on RELAY_TYPE config."""
    global _controller_instance

    if _controller_instance is not None:
        return _controller_instance

    with _controller_lock:
        if _controller_instance is not None:
            return _controller_instance

        relay_type = settings.RELAY_TYPE.lower()

        if relay_type == "http":
            _controller_instance = HTTPRelayController()
        elif relay_type == "usb":
            _controller_instance = USBRelayController()
        elif relay_type == "gpio":
            _controller_instance = GPIORelayController()
        elif relay_type == "simulated":
            _controller_instance = SimulatedRelayController()
        else:
            log.warning("Unknown RELAY_TYPE '%s' — falling back to simulated", relay_type)
            _controller_instance = SimulatedRelayController()

        log.info("Relay controller initialized: %s (%s)", type(_controller_instance).__name__, relay_type)
        return _controller_instance
