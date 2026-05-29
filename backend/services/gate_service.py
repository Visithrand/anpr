"""
backend/services/gate_service.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Gate control service for Boom Barrier via Modbus TCP.
"""
import logging
import threading
import time
from pymodbus.client.sync import ModbusTcpClient

from backend.config import settings
from backend.utils.database import SessionLocal
from backend.models.models import SystemLog

log = logging.getLogger(__name__)

class GateService:
    def __init__(self):
        self.host = "192.168.1.110"
        self.port = 502
        self.coil = 512
        self.duration = settings.GATE_OPEN_DURATION
        
        # Parse GATE_API_URL (expected format: ip:port)
        if settings.GATE_API_URL:
            parts = settings.GATE_API_URL.replace("http://", "").replace("https://", "").split(":")
            if len(parts) == 2:
                self.host = parts[0]
                self.port = int(parts[1])
            elif len(parts) == 1 and parts[0]:
                self.host = parts[0]
                
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
        # Modbus client might have disconnected, try writing/reading a dummy or just checking socket
        # Pymodbus sync client doesn't have a reliable is_socket_open sometimes without attempting IO
        # We'll just rely on the connect() state or attempt reconnect on failure.
        return True

    def _write_coil(self, state: bool):
        with self._lock:
            try:
                if not self.client or not self.client.connect():
                    self.connect()
                if self.client:
                    self.client.write_coil(self.coil, state, unit=1)
                    return True
            except Exception as e:
                log.error(f"Failed to write coil {self.coil}: {e}")
                self._log_system_error(f"Failed to write coil {self.coil}: {e}")
            return False

    def open_gate(self, duration_seconds: int = None):
        if duration_seconds is None:
            duration_seconds = self.duration
            
        def _trigger():
            log.info(f"Opening gate (coil {self.coil}) for {duration_seconds}s")
            if self._write_coil(True):
                time.sleep(duration_seconds)
                self._write_coil(False)
                log.info("Gate closed.")
            else:
                log.error("Gate failed to open.")
                
        threading.Thread(target=_trigger, daemon=True).start()

# Singleton instance
gate_service = GateService()
