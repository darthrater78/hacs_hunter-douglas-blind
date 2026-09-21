"""Hunter Douglas PowerView Gen 3 over BLE (no gateway, no cloud)."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .hub import PowerViewHub

PLATFORMS = [Platform.SENSOR, Platform.BUTTON]

type PowerViewConfigEntry = ConfigEntry[PowerViewHub]


async def async_setup_entry(hass: HomeAssistant, entry: PowerViewConfigEntry) -> bool:
    """Set up a PowerView home: read-only, unencrypted data only."""
    hub = PowerViewHub(hass, entry)
    entry.runtime_data = hub
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await hub.async_start()
    entry.async_on_unload(hub.async_stop)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PowerViewConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
