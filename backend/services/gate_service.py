"""
backend/services/gate_service.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Gate control service for Boom Barrier via Modbus TCP.

Supports separate coil addresses for entry and exit gates
on the same Modbus TCP relay (shared IP + port).

Configuration (from .env / settings):
  RELAY_IP           = 10.10.1.100
  RELAY_PORT         = 506
  ENTRY_RELAY_COIL   = 512
  EXIT_RELAY_COIL    = 513
  GATE_OPEN_DURATION = 10
"""
import logging
import threading
import time
from pymodbus.client import ModbusTcpClient

from backend.config import settings
from backend.utils.database import SessionLocal
from backend.models.models import SystemLog

log = logging.getLogger(__name__)

class GateService:
    def __init__(self):
        self.host = settings.RELAY_IP if settings.RELAY_IP else "10.10.1.100"
        self.port = int(settings.RELAY_PORT) if settings.RELAY_PORT else 506
        self.entry_coil = settings.ENTRY_RELAY_COIL   # 512
        self.exit_coil = settings.EXIT_RELAY_COIL      # 513
        self.duration = settings.GATE_OPEN_DURATION
        
        self.client = None
        self._lock = threading.Lock()
        
    def _log_system_error(self, message: str):
        try:
            with SessionLocal() as db:
                db.add(SystemLog(
                    service_name="gate_service",
                    level="ERROR",
                    message=message
                ))
                db.commit()
        except Exception as e:
            log.error(f"Failed to log to SystemLog: {e}")

    def connect(self):
        try:
            self.client = ModbusTcpClient(self.host, port=self.port)
            if self.client.connect():
                log.info(f"✅ Modbus Gate connected at {self.host}:{self.port}")
                return True
            log.error(f"❌ Modbus Gate connection failed at {self.host}:{self.port}")
            self._log_system_error(f"Modbus connection failed at {self.host}:{self.port}")
            return False
        except Exception as e:
            log.error(f"❌ Modbus Gate error: {e}")
            self._log_system_error(f"Modbus connection error: {e}")
            return False

    def is_connected(self) -> bool:
        if not self.client:
            return self.connect()
        # Pymodbus sync client doesn't have a reliable is_socket_open sometimes without attempting IO
        # We'll just rely on the connect() state or attempt reconnect on failure.
        return True

    def _write_coil(self, coil: int, state: bool):
        with self._lock:
            try:
                if not self.client or not self.client.connect():
                    self.connect()
                if self.client:
                    self.client.write_coil(coil, state, unit=1)
                    return True
            except Exception as e:
                log.error(f"Failed to write coil {coil}: {e}")
                self._log_system_error(f"Failed to write coil {coil}: {e}")
            return False

    def _get_coil(self, gate_type: str = "entry") -> int:
        """Return the coil address for the given gate type."""
        if gate_type == "exit":
            return self.exit_coil
        return self.entry_coil

    def open_gate(self, gate_type: str = "entry", duration_seconds: int = None):
        """
        Open a gate by energizing the appropriate Modbus coil.
        
        Args:
            gate_type: "entry" (coil 512) or "exit" (coil 513)
            duration_seconds: how long to hold the gate open
        """
        if duration_seconds is None:
            duration_seconds = self.duration
        
        coil = self._get_coil(gate_type)
            
        def _trigger():
            log.info(f"Opening {gate_type} gate (coil {coil}) for {duration_seconds}s")
            if self._write_coil(coil, True):
                time.sleep(duration_seconds)
                self._write_coil(coil, False)
                log.info(f"{gate_type.capitalize()} gate closed (coil {coil}).")
            else:
                log.error(f"{gate_type.capitalize()} gate failed to open (coil {coil}).")
                
        threading.Thread(target=_trigger, daemon=True).start()

# Singleton instance
gate_service = GateService()
