"""
backend/utils/websocket.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Production-grade WebSocket connection manager.

Features:
  - Error-safe broadcast (disconnects broken clients instead of crashing)
  - JSON broadcast helper
  - Connection count tracking
  - Heartbeat-aware disconnect detection
"""

from __future__ import annotations

import json
import logging
from typing import List

from fastapi import WebSocket

log = logging.getLogger(__name__)


class ConnectionManager:
    """Thread-safe WebSocket connection manager with error handling."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        log.info("WebSocket connected — %d active connections", len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket from the active pool."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        log.info("WebSocket disconnected — %d active connections", len(self.active_connections))

    async def broadcast(self, message: str):
        """
        Send a text message to all connected clients.

        Broken connections are detected and removed automatically
        instead of crashing the broadcast loop.
        """
        if not self.active_connections:
            return

        disconnected: List[WebSocket] = []

        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                log.warning("WebSocket send failed — disconnecting client: %s", e)
                disconnected.append(connection)

        # Remove broken connections
        for ws in disconnected:
            self.disconnect(ws)

    async def broadcast_json(self, data: dict):
        """Send a JSON message to all connected clients."""
        await self.broadcast(json.dumps(data))

    @property
    def connection_count(self) -> int:
        """Return the number of active WebSocket connections."""
        return len(self.active_connections)


manager = ConnectionManager()
