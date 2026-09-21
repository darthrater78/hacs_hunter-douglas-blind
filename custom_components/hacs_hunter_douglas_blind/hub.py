"""Collects everything a PowerView shade shares without encryption.

Two sources, both keyless:
* advertisements (push, no connection): homeId, typeId, position, tilt, status byte, RSSI
* GATT reads (poll, needs a connection): battery level and Device Information
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime

from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    CHAR_BATTERY_LEVEL,
    CONF_HOME_ID,
    DEVICE_INFO_CHARS,
    DOMAIN,
    GATT_POLL_INTERVAL,
    MANUFACTURER_ID,
    MAX_SHADES,
)
from .protocol import Advertisement, parse_advertisement

_LOGGER = logging.getLogger(__name__)

# What a failed BLE read/connect can raise; anything else is a bug and should surface.
_BLE_ERRORS = (BleakError, TimeoutError, OSError)


def _clean_text(raw: bytes) -> str:
    """Printable text from a GATT string; the peer may be a spoofed device."""
    text = raw.decode("utf-8", "replace")
    return "".join(ch for ch in text if ch.isprintable()).strip()[:64]


@dataclass
class ShadeData:
    """Latest known state of one shade (one BLE address)."""

    address: str
    name: str
    advert: Advertisement
    rssi: int | None = None
    last_seen: datetime = field(default_factory=dt_util.utcnow)
    battery: int | None = None
    battery_supported: bool | None = None  # None = not yet tried
    device_info: dict[str, str] = field(default_factory=dict)
    last_raw: str = ""


class PowerViewHub:
    """Tracks every shade belonging to one homeId."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.home_id: int = entry.data[CONF_HOME_ID]
        self.shades: dict[str, ShadeData] = {}
        self._unsubs: list[CALLBACK_TYPE] = []
        # One GATT connection at a time: adapters and proxies have few slots.
        self._gatt_lock = asyncio.Lock()

    @property
    def signal_new(self) -> str:
        return f"{DOMAIN}_new_{self.entry.entry_id}"

    def signal_update(self, address: str) -> str:
        return f"{DOMAIN}_update_{self.entry.entry_id}_{address}"

    async def async_start(self) -> None:
        # Seed from what the Bluetooth stack has already seen.
        for info in bluetooth.async_discovered_service_info(self.hass, False):
            self._handle_advert(info, None)
        self._unsubs.append(
            bluetooth.async_register_callback(
                self.hass,
                self._handle_advert,
                bluetooth.BluetoothCallbackMatcher(
                    manufacturer_id=MANUFACTURER_ID, connectable=False
                ),
                bluetooth.BluetoothScanningMode.PASSIVE,
            )
        )
        self._unsubs.append(
            async_track_time_interval(
                self.hass, self._async_poll_all, GATT_POLL_INTERVAL
            )
        )

    @callback
    def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()

    @callback
    def _handle_advert(
        self,
        info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange | None,
    ) -> None:
        payload = info.manufacturer_data.get(MANUFACTURER_ID)
        advert = parse_advertisement(payload) if payload else None
        if advert is None or advert.home_id != self.home_id:
            return
        shade = self.shades.get(info.address)
        is_new = shade is None
        if is_new:
            if len(self.shades) >= MAX_SHADES:
                # Anyone can advertise our homeId; bound what we will create.
                _LOGGER.warning("Ignoring %s: more than %s shades", info.address, MAX_SHADES)
                return
            shade = ShadeData(info.address, info.name or info.address, advert)
            self.shades[info.address] = shade
        shade.advert = advert
        shade.rssi = info.rssi
        shade.last_seen = dt_util.utcnow()
        shade.last_raw = payload.hex()
        if is_new:
            async_dispatcher_send(self.hass, self.signal_new, shade)
            self.entry.async_create_background_task(
                self.hass, self.async_poll_gatt(shade), f"{DOMAIN}_poll_{info.address}"
            )
        else:
            async_dispatcher_send(self.hass, self.signal_update(info.address))

    async def _async_poll_all(self, _now: datetime) -> None:
        for shade in list(self.shades.values()):
            await self.async_poll_gatt(shade)

    async def async_poll_gatt(self, shade: ShadeData) -> None:
        """Read battery + Device Information. Best effort; failures are retried next poll."""
        async with self._gatt_lock:
            await self._async_read_gatt(shade)
        async_dispatcher_send(self.hass, self.signal_update(shade.address))

    async def _async_read_gatt(self, shade: ShadeData) -> None:
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, shade.address, connectable=True
        )
        if ble_device is None:
            _LOGGER.debug("%s: no connectable adapter/proxy in range", shade.address)
            return
        try:
            client = await establish_connection(
                BleakClientWithServiceCache, ble_device, shade.address
            )
        except _BLE_ERRORS:
            _LOGGER.debug("%s: GATT connect failed", shade.address, exc_info=True)
            return
        try:
            await self._read_battery(client, shade)
            await self._read_device_info(client, shade)
        finally:
            try:
                await client.disconnect()
            except _BLE_ERRORS:
                _LOGGER.debug("%s: disconnect failed", shade.address, exc_info=True)

    async def _read_battery(self, client: BleakClientWithServiceCache, shade: ShadeData) -> None:
        try:
            raw = bytes(await client.read_gatt_char(CHAR_BATTERY_LEVEL))
        except _BLE_ERRORS:
            # Connected but no readable 0x2A19 (mains-powered shades are an open
            # question in the framework's notes).
            shade.battery_supported = False
            _LOGGER.debug("%s: battery read failed", shade.address, exc_info=True)
            return
        if not raw:
            shade.battery_supported = False
            return
        shade.battery = min(raw[0], 100)
        shade.battery_supported = True

    async def _read_device_info(self, client: BleakClientWithServiceCache, shade: ShadeData) -> None:
        for key, uuid in DEVICE_INFO_CHARS.items():
            try:
                value = bytes(await client.read_gatt_char(uuid))
            except _BLE_ERRORS:
                _LOGGER.debug("%s: %s not readable", shade.address, key)
                continue
            shade.device_info[key] = _clean_text(value)
