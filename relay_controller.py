from pymodbus.client.sync import ModbusTcpClient
import threading, time, os

class BoomBarrierRelay:
    RELAY_COILS = {1:512, 2:513, 3:514, 4:515, 5:516}

    def __init__(self):
        self.ip = os.getenv("RELAY_IP", "192.168.1.110")
        self.port = int(os.getenv("RELAY_PORT", 502))
        self.unit = int(os.getenv("RELAY_UNIT", 1))
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

    def open_barrier(self, relay_num=1, duration_ms=3000):
        coil = self.RELAY_COILS.get(relay_num, 512)
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
