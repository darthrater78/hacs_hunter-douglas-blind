"""A button per shade that refreshes the battery on demand."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .hub import PowerViewHub, ShadeData

REFRESH_BATTERY = ButtonEntityDescription(
    key="refresh_battery",
    translation_key="refresh_battery",
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    hub: PowerViewHub = entry.runtime_data

    @callback
    def _add(shade: ShadeData) -> None:
        async_add_entities([RefreshBatteryButton(hub, shade.address)])

    for shade in list(hub.shades.values()):
        _add(shade)
    entry.async_on_unload(async_dispatcher_connect(hass, hub.signal_new, _add))


class RefreshBatteryButton(ButtonEntity):
    """Connects to the shade now and reads the battery (and device info)."""

    _attr_has_entity_name = True
    entity_description = REFRESH_BATTERY

    def __init__(self, hub: PowerViewHub, address: str) -> None:
        self._hub = hub
        self._address = address
        self._attr_unique_id = f"{address}_{REFRESH_BATTERY.key}"
        # Same identifiers as the sensors, so it lands on the same device.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            connections={(CONNECTION_BLUETOOTH, address)},
        )

    async def async_press(self) -> None:
        failure = await self._hub.async_poll_gatt(self._hub.shades[self._address])
        if failure:
            raise HomeAssistantError(f"Could not refresh the battery: {failure}")
