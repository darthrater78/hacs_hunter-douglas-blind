"""Config flow: Bluetooth discovery of PowerView Gen 3 shades, one entry per home."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import CONF_HOME_ID, DOMAIN, MANUFACTURER_ID
from .protocol import parse_advertisement


class PowerViewConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._home_id: int | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle a shade seen by the Bluetooth integration."""
        payload = discovery_info.manufacturer_data.get(MANUFACTURER_ID)
        advert = parse_advertisement(payload) if payload else None
        if advert is None:
            return self.async_abort(reason="not_supported")
        # The homeId is shared by every shade in a home and shares one write
        # keystream, so it is the natural unique ID for an entry.
        await self.async_set_unique_id(str(advert.home_id))
        self._abort_if_unique_id_configured()
        self._home_id = advert.home_id
        self.context["title_placeholders"] = {"home_id": str(advert.home_id)}
        return await self.async_step_confirm()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manual add: pick from homes currently seen in Bluetooth range."""
        homes: set[int] = set()
        for info in async_discovered_service_info(self.hass, False):
            payload = info.manufacturer_data.get(MANUFACTURER_ID)
            advert = parse_advertisement(payload) if payload else None
            if advert:
                homes.add(advert.home_id)
        homes -= {
            e.data[CONF_HOME_ID] for e in self._async_current_entries(include_ignore=False)
        }
        if not homes:
            return self.async_abort(reason="no_devices_found")
        if user_input is not None:
            self._home_id = int(user_input[CONF_HOME_ID])
            await self.async_set_unique_id(str(self._home_id))
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"PowerView home {self._home_id}",
                data={CONF_HOME_ID: self._home_id},
            )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_HOME_ID): vol.In({str(h): f"Home {h}" for h in sorted(homes)})}
            ),
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm adding the discovered home."""
        if user_input is not None:
            return self.async_create_entry(
                title=f"PowerView home {self._home_id}",
                data={CONF_HOME_ID: self._home_id},
            )
        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"home_id": str(self._home_id)},
        )
