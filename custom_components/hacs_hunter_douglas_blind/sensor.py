"""Sensors for every unencrypted value a shade exposes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .hub import PowerViewHub, ShadeData
from .protocol import Capability, capability_for_type


@dataclass(frozen=True, kw_only=True)
class ShadeSensorDescription(SensorEntityDescription):
    value_fn: Callable[[ShadeData, Capability], Any]
    applies_fn: Callable[[Capability], bool] = lambda cap: True


DIAG = EntityCategory.DIAGNOSTIC

# A sensor state is capped at 255 characters and a failure reason carries a
# truncated exception string, so it is clipped rather than dropped by HA.
MAX_STATE_LENGTH = 255


def gatt_status(shade: ShadeData) -> str | None:
    """Outcome of the last GATT attempt: None before the first one, else why it failed."""
    if shade.last_attempt is None:
        return None
    return (shade.last_error or "ok")[:MAX_STATE_LENGTH]


SENSORS: tuple[ShadeSensorDescription, ...] = (
    ShadeSensorDescription(
        key="primary",
        translation_key="primary",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda s, c: s.advert.primary,
        applies_fn=lambda c: c.primary,
    ),
    ShadeSensorDescription(
        key="secondary",
        translation_key="secondary",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda s, c: s.advert.secondary,
        applies_fn=lambda c: c.secondary,
    ),
    ShadeSensorDescription(
        key="tilt",
        translation_key="tilt",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s, c: s.advert.tilt,
        applies_fn=lambda c: c.tilt,
    ),
    ShadeSensorDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=DIAG,
        value_fn=lambda s, c: s.battery,
    ),
    ShadeSensorDescription(
        key="status_byte",
        translation_key="status_byte",
        entity_category=DIAG,
        entity_registry_enabled_default=False,
        # Advertisement byte 8. The framework calls it "velocity" but a
        # stationary shade reads 0xC0, so it looks like flags -- expose raw.
        value_fn=lambda s, c: s.advert.velocity,
    ),
    ShadeSensorDescription(
        key="type_id",
        translation_key="type_id",
        entity_category=DIAG,
        value_fn=lambda s, c: s.advert.type_id,
    ),
    ShadeSensorDescription(
        key="capability",
        translation_key="capability",
        entity_category=DIAG,
        value_fn=lambda s, c: c.name,
    ),
    ShadeSensorDescription(
        key="gatt_status",
        translation_key="gatt_status",
        entity_category=DIAG,
        value_fn=lambda s, c: gatt_status(s),
    ),
    ShadeSensorDescription(
        key="last_gatt_attempt",
        translation_key="last_gatt_attempt",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=DIAG,
        entity_registry_enabled_default=False,
        value_fn=lambda s, c: s.last_attempt,
    ),
    ShadeSensorDescription(
        key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=DIAG,
        entity_registry_enabled_default=False,
        value_fn=lambda s, c: s.rssi,
    ),
    ShadeSensorDescription(
        key="raw_advertisement",
        translation_key="raw_advertisement",
        entity_category=DIAG,
        entity_registry_enabled_default=False,
        value_fn=lambda s, c: s.last_raw,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    hub: PowerViewHub = entry.runtime_data

    @callback
    def _add(shade: ShadeData) -> None:
        cap, _ = capability_for_type(shade.advert.type_id)
        async_add_entities(
            ShadeSensor(hub, shade.address, d) for d in SENSORS if d.applies_fn(cap)
        )

    for shade in list(hub.shades.values()):
        _add(shade)
    entry.async_on_unload(async_dispatcher_connect(hass, hub.signal_new, _add))


class ShadeSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    entity_description: ShadeSensorDescription

    def __init__(self, hub: PowerViewHub, address: str, desc: ShadeSensorDescription) -> None:
        self._hub = hub
        self._address = address
        self.entity_description = desc
        self._attr_unique_id = f"{address}_{desc.key}"

    @property
    def _shade(self) -> ShadeData:
        return self._hub.shades[self._address]

    @property
    def device_info(self) -> DeviceInfo:
        s = self._shade
        info = s.device_info
        return DeviceInfo(
            identifiers={(DOMAIN, s.address)},
            connections={(CONNECTION_BLUETOOTH, s.address)},
            name=f"PowerView shade {s.address[-5:].replace(':', '')}",
            manufacturer=info.get("manufacturer") or "Hunter Douglas",
            model=info.get("model") or f"PowerView Gen 3 type {s.advert.type_id}",
            model_id=str(s.advert.type_id),
            sw_version=info.get("firmware"),
            hw_version=info.get("hardware"),
            serial_number=info.get("serial"),
        )

    @property
    def available(self) -> bool:
        # Battery is only meaningful once a GATT read has succeeded.
        if self.entity_description.key == "battery":
            return self._shade.battery is not None
        return True

    @property
    def native_value(self) -> Any:
        cap, _ = capability_for_type(self._shade.advert.type_id)
        return self.entity_description.value_fn(self._shade, cap)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._hub.signal_update(self._address), self.async_write_ha_state
            )
        )
