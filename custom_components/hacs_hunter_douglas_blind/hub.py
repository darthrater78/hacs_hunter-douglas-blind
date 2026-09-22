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

from bleak.backends.device import BLEDevice
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
    CONNECT_ATTEMPTS,
    DEVICE_INFO_CHARS,
    DOMAIN,
    GATT_POLL_INTERVAL,
    MANUFACTURER_ID,
    MAX_SHADES,
    WARN_INTERVAL,
)
from .protocol import Advertisement, parse_advertisement

_LOGGER = logging.getLogger(__name__)

# What a failed BLE read/connect can raise; anything else is a bug and should surface.
_BLE_ERRORS = (BleakError, TimeoutError, OSError)


def _printable(text: str, limit: int) -> str:
    """Printable, bounded text. Anything sourced from the peer goes through this."""
    return "".join(ch for ch in text if ch.isprintable()).strip()[:limit]


def _clean_text(raw: bytes) -> str:
    """Printable text from a GATT string; the peer may be a spoofed device."""
    return _printable(raw.decode("utf-8", "replace"), 64)


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
    # Rate limit for the connect warning: what kind of failure, and when.
    warned_kind: str | None = None
    warned_at: datetime | None = None
    # Why the last GATT attempt failed, and when it ran. Exposed as diagnostic
    # sensors so a failing read can be seen without reading the log.
    last_error: str | None = None
    last_attempt: datetime | None = None
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

    async def async_poll_gatt(
        self, shade: ShadeData, *, wait: float | None = None
    ) -> str | None:
        """Read battery + Device Information. Best effort; failures are retried next poll.

        Returns None when the battery was read, else a short reason it was not.

        One shade is read at a time, so a caller can queue behind another
        shade's connect attempts. `wait` bounds that queueing: background reads
        wait their turn (the default), while a caller someone is watching passes
        a timeout and gets an answer instead of a spinner. A timeout here is not
        a radio failure, so it is reported without touching `last_error`.
        """
        try:
            await asyncio.wait_for(self._gatt_lock.acquire(), wait)
        except TimeoutError:
            _LOGGER.debug("%s: another GATT read still holds the radio", shade.address)
            return "another shade is being read right now; try again in a moment"
        try:
            failure = await self._async_read_gatt(shade)
        finally:
            self._gatt_lock.release()
        async_dispatcher_send(self.hass, self.signal_update(shade.address))
        return failure

    async def _async_read_gatt(self, shade: ShadeData) -> str | None:
        """Run one attempt, recording its outcome on the shade."""
        shade.last_attempt = dt_util.utcnow()
        shade.last_error = await self._async_try_read(shade)
        return shade.last_error

    def _scanner_source(self, address: str) -> str:
        """Which radio HA would connect through: a proxy's MAC, or a local adapter.

        Worth logging on every attempt: once a second proxy or a USB dongle is
        added, "which radio was this?" is the first question about a failure,
        and the answer can change between one attempt and the next.
        """
        info = bluetooth.async_last_service_info(self.hass, address, connectable=True)
        return info.source if info is not None else "unknown"

    def _should_warn(self, shade: ShadeData, kind: str) -> bool:
        """Warn on a new kind of failure, and again once an hour while it persists.

        Keyed on the exception type rather than the message: a bleak connect
        error embeds the attempt count and the age of the last advertisement, so
        keying on the text would make every attempt look new and warn every
        time. The full message still reaches the log line and the GATT status
        sensor -- only the decision to warn is coarsened.
        """
        now = dt_util.utcnow()
        if (
            shade.warned_kind == kind
            and shade.warned_at is not None
            and now - shade.warned_at < WARN_INTERVAL
        ):
            return False
        shade.warned_kind = kind
        shade.warned_at = now
        return True

    async def _async_try_read(self, shade: ShadeData) -> str | None:
        # Home Assistant answers from its advertisement history, so a device
        # comes back even when no scanner is registered -- which is what a poll
        # right after a restart sees, before any proxy has connected. Without
        # this check every attempt is spent against a stack that has no radio.
        if not bluetooth.async_scanner_count(self.hass, connectable=True):
            _LOGGER.debug("%s: no Bluetooth scanner registered yet", shade.address)
            return "Home Assistant has no Bluetooth adapter or proxy registered yet"

        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, shade.address, connectable=True
        )
        if ble_device is None:
            _LOGGER.debug("%s: no connectable adapter/proxy in range", shade.address)
            return "no connectable Bluetooth adapter or proxy is in range of the shade"

        source = self._scanner_source(shade.address)
        _LOGGER.debug(
            "%s: connecting via %s (rssi=%s)", shade.address, source, shade.rssi
        )

        def _fresh_device() -> BLEDevice:
            # Re-resolved per attempt: HA picks the best connectable radio at
            # call time, so a retry can move to another proxy or a dongle added
            # since. Reusing one BLEDevice pins every retry to the first radio.
            return (
                bluetooth.async_ble_device_from_address(
                    self.hass, shade.address, connectable=True
                )
                or ble_device
            )

        try:
            client = await establish_connection(
                BleakClientWithServiceCache,
                ble_device,
                shade.address,
                max_attempts=CONNECT_ATTEMPTS,
                ble_device_callback=_fresh_device,
            )
        except _BLE_ERRORS as err:
            # Warn with what we know about the link, so the cause is visible
            # without debug logging -- rate limited, not once ever, so the
            # steady-state failure is not hidden behind the first one seen.
            # `connectable=True` below is a property of
            # the *scanner* that heard the shade, not of the shade's advertising
            # PDU -- it says a connection-capable radio is in range, and nothing
            # about whether the shade is accepting connections.
            reason = f"the connection failed ({type(err).__name__}: {_printable(str(err), 160)})"
            log = (
                _LOGGER.warning
                if self._should_warn(shade, type(err).__name__)
                else _LOGGER.debug
            )
            log(
                "%s: GATT connect failed: %s (via=%s, details=%s, rssi=%s, "
                "still heard by a connection-capable scanner=%s)",
                shade.address,
                err,
                source,
                getattr(ble_device, "details", None),
                shade.rssi,
                bluetooth.async_last_service_info(
                    self.hass, shade.address, connectable=True
                )
                is not None,
            )
            return reason
        try:
            await self._read_battery(client, shade)
            await self._read_device_info(client, shade)
        finally:
            try:
                await client.disconnect()
            except _BLE_ERRORS:
                _LOGGER.debug("%s: disconnect failed", shade.address, exc_info=True)
        if shade.battery_supported:
            return None
        return "connected, but the shade did not return a readable battery level"

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
