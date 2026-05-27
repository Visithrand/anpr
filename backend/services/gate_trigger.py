"""
backend/services/gate_trigger.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
High-level gate trigger functions — thin wrappers around the RelayController.

These functions are called by the entry/exit routes and live dashboard.
They preserve the original API surface for backward compatibility.

Usage:
    gate = await open_entry_gate()
    gate = await open_exit_gate()
"""

from __future__ import annotations

import logging

from backend.services.relay_controller import get_relay_controller

log = logging.getLogger(__name__)


async def open_entry_gate() -> dict:
    """Trigger the ENTRY boom barrier to open."""
    log.info("GATE TRIGGER → Opening ENTRY barrier")
    controller = get_relay_controller()
    return controller.open_gate("entry")


async def open_exit_gate() -> dict:
    """Trigger the EXIT boom barrier to open."""
    log.info("GATE TRIGGER → Opening EXIT barrier")
    controller = get_relay_controller()
    return controller.open_gate("exit")


async def close_entry_gate() -> dict:
    """Manually close the ENTRY barrier."""
    log.info("GATE TRIGGER → Closing ENTRY barrier")
    controller = get_relay_controller()
    return controller.close_gate("entry")


async def close_exit_gate() -> dict:
    """Manually close the EXIT barrier."""
    log.info("GATE TRIGGER → Closing EXIT barrier")
    controller = get_relay_controller()
    return controller.close_gate("exit")
