from pymodbus.client import ModbusTcpClient
import threading, time, os

class BoomBarrierRelay:
    def __init__(self):
        self.ip = os.getenv("RELAY_IP", "192.168.1.110")
        self.port = int(os.getenv("RELAY_PORT", 502))
        self.unit = int(os.getenv("RELAY_UNIT", 1))
        # Coil addresses from environment / config
        self.entry_coil = int(os.getenv("ENTRY_RELAY_COIL", 512))
        self.exit_coil = int(os.getenv("EXIT_RELAY_COIL", 513))
        self.client = None
        self._lock = threading.Lock()

    def connect(self):
        try:
            self.client = ModbusTcpClient(self.ip, port=self.port)
            if self.client.connect():
                print(f"✅ Relay connected at {self.ip}:{self.port}")
                return True
            print("❌ Relay connection failed")
            return False
        except Exception as e:
            print(f"❌ Relay error: {e}")
            return False

    def _write_coil(self, coil_addr, state):
        with self._lock:
            if self.client:
                self.client.write_coil(coil_addr, state, unit=self.unit)

    def open_barrier(self, gate_type="entry", duration_ms=3000):
        """
        Open a barrier by gate type.
        
        Args:
            gate_type: "entry" (coil 512) or "exit" (coil 513)
            duration_ms: how long to hold the relay open in milliseconds
        """
        if gate_type == "exit":
            coil = self.exit_coil
        else:
            coil = self.entry_coil
            
        def _trigger():
            self._write_coil(coil, True)
            time.sleep(duration_ms / 1000)
            self._write_coil(coil, False)
        threading.Thread(target=_trigger, daemon=True).start()

    def disconnect(self):
        if self.client:
            self.client.close()

barrier = BoomBarrierRelay()
barrier.connect()
