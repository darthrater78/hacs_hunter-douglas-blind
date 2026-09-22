"""Home Assistant integration tests. Run with pytest (see requirements_test.txt)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.config_entries import SOURCE_BLUETOOTH  # noqa: E402
from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402
from homeassistant.exceptions import HomeAssistantError  # noqa: E402
from homeassistant.helpers import entity_registry as er  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.hacs_hunter_douglas_blind.const import CONF_HOME_ID, DOMAIN  # noqa: E402

from .conftest import make_info  # noqa: E402

# Real payloads from a Duette TDBU (type 8, home 63548), 2026-09-21.
MOVED = "3CF8080030FA0000C0"  # primary clamps to 100, secondary 6.25
CLOSED = "3CF8080000090000C0"  # primary 0, secondary 0.225
OTHER_HOME = "0100080000090000C0"

HUB = "custom_components.hacs_hunter_douglas_blind.hub.bluetooth"


@pytest.fixture(autouse=True)
def _bluetooth_present(hass: HomeAssistant):
    """The Bluetooth stack is not started in tests; mark its components loaded."""
    hass.config.components.update({"bluetooth", "bluetooth_adapters"})


async def _setup(hass: HomeAssistant, seen: list):
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOME_ID: 63548}, unique_id="63548")
    entry.add_to_hass(hass)
    callbacks: list = []

    def register(_hass, cb, *_a, **_k):
        callbacks.append(cb)
        return MagicMock()

    with (
        patch(f"{HUB}.async_discovered_service_info", return_value=seen),
        patch(f"{HUB}.async_register_callback", side_effect=register),
        patch(f"{HUB}.async_ble_device_from_address", return_value=None),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry, callbacks[0]


def _state(hass: HomeAssistant, unique_suffix: str):
    reg = er.async_get(hass)
    entity_id = reg.async_get_entity_id("sensor", DOMAIN, f"C6:83:B4:47:08:51_{unique_suffix}")
    assert entity_id, unique_suffix
    return hass.states.get(entity_id)


async def test_entities_created_for_top_down_bottom_up(hass: HomeAssistant):
    await _setup(hass, [make_info(MOVED)])
    assert float(_state(hass, "primary").state) == 100.0
    assert float(_state(hass, "secondary").state) == pytest.approx(6.25)
    assert _state(hass, "type_id").state == "8"
    assert _state(hass, "capability").state == "top_down_bottom_up"
    # TDBU has no tilt rail, so no tilt entity is created.
    reg = er.async_get(hass)
    assert reg.async_get_entity_id("sensor", DOMAIN, "C6:83:B4:47:08:51_tilt") is None


async def test_update_from_new_advertisement(hass: HomeAssistant):
    _entry, cb = await _setup(hass, [make_info(CLOSED)])
    assert float(_state(hass, "primary").state) == 0.0
    cb(make_info(MOVED), None)
    await hass.async_block_till_done()
    assert float(_state(hass, "primary").state) == 100.0


async def test_other_home_is_ignored(hass: HomeAssistant):
    _entry, cb = await _setup(hass, [])
    cb(make_info(OTHER_HOME), None)
    await hass.async_block_till_done()
    assert er.async_get(hass).entities.get_entries_for_config_entry_id(_entry.entry_id) == []


async def test_battery_unavailable_until_read(hass: HomeAssistant):
    await _setup(hass, [make_info(CLOSED)])
    assert _state(hass, "battery").state == "unavailable"


async def test_bluetooth_discovery_flow_creates_entry(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=make_info(MOVED)
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOME_ID: 63548}


async def test_bluetooth_discovery_aborts_for_duplicate_home(hass: HomeAssistant):
    MockConfigEntry(domain=DOMAIN, data={CONF_HOME_ID: 63548}, unique_id="63548").add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=make_info(MOVED)
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


class _FakeClient:
    """Stands in for a connected BLE client: battery 63%, some device info."""

    values = {
        "00002a19-0000-1000-8000-00805f9b34fb": bytes([63]),
        "00002a29-0000-1000-8000-00805f9b34fb": b"Hunter Douglas\x00",
        "00002a26-0000-1000-8000-00805f9b34fb": b"1.2.3",
    }

    async def read_gatt_char(self, uuid: str) -> bytearray:
        from bleak.exc import BleakError

        try:
            return bytearray(self.values[uuid])
        except KeyError:
            raise BleakError("not readable") from None

    async def disconnect(self) -> None:
        return None


async def test_gatt_poll_reads_battery_and_device_info(hass: HomeAssistant):
    entry, _cb = await _setup(hass, [make_info(CLOSED)])
    hub = entry.runtime_data
    shade = hub.shades["C6:83:B4:47:08:51"]

    async def connect(*_a, **_k):
        return _FakeClient()

    with (
        patch(f"{HUB}.async_ble_device_from_address", return_value=MagicMock()),
        patch(f"{HUB}.async_last_service_info", return_value=None),
        patch("custom_components.hacs_hunter_douglas_blind.hub.establish_connection", connect),
    ):
        await hub.async_poll_gatt(shade)
        await hass.async_block_till_done()

    assert _state(hass, "battery").state == "63"
    assert shade.device_info == {
        "manufacturer": "Hunter Douglas",
        "firmware": "1.2.3",
    }


async def test_gatt_device_info_drops_control_characters(hass: HomeAssistant):
    """A spoofed device must not smuggle control characters into the registry."""
    entry, _cb = await _setup(hass, [make_info(CLOSED)])
    hub = entry.runtime_data
    shade = hub.shades["C6:83:B4:47:08:51"]

    class _Hostile(_FakeClient):
        values = {
            "00002a29-0000-1000-8000-00805f9b34fb": b"Evil\x1b[31m\nCorp\x00\x07",
        }

    async def connect(*_a, **_k):
        return _Hostile()

    with (
        patch(f"{HUB}.async_ble_device_from_address", return_value=MagicMock()),
        patch(f"{HUB}.async_last_service_info", return_value=None),
        patch("custom_components.hacs_hunter_douglas_blind.hub.establish_connection", connect),
    ):
        await hub.async_poll_gatt(shade)

    assert shade.device_info == {"manufacturer": "Evil[31mCorp"}


async def test_gatt_failure_leaves_battery_unavailable(hass: HomeAssistant):
    from bleak.exc import BleakError

    entry, _cb = await _setup(hass, [make_info(CLOSED)])
    hub = entry.runtime_data

    async def connect(*_a, **_k):
        raise BleakError("out of slots")

    with (
        patch(f"{HUB}.async_ble_device_from_address", return_value=MagicMock()),
        patch(f"{HUB}.async_last_service_info", return_value=None),
        patch("custom_components.hacs_hunter_douglas_blind.hub.establish_connection", connect),
    ):
        await hub.async_poll_gatt(hub.shades["C6:83:B4:47:08:51"])
    assert _state(hass, "battery").state == "unavailable"


async def test_spoofed_shades_are_capped(hass: HomeAssistant):
    """Anyone can advertise our homeId; entity creation must stay bounded."""
    _entry, cb = await _setup(hass, [])
    with (
        patch("custom_components.hacs_hunter_douglas_blind.hub.MAX_SHADES", 2),
        patch(f"{HUB}.async_ble_device_from_address", return_value=None),
    ):
        for i in range(5):
            cb(make_info(CLOSED, address=f"AA:BB:CC:DD:EE:{i:02X}"), None)
        await hass.async_block_till_done()
    assert len(_entry.runtime_data.shades) == 2


def _button_id(hass: HomeAssistant) -> str:
    reg = er.async_get(hass)
    entity_id = reg.async_get_entity_id(
        "button", DOMAIN, "C6:83:B4:47:08:51_refresh_battery"
    )
    assert entity_id
    return entity_id


async def test_refresh_button_reads_battery_now(hass: HomeAssistant):
    await _setup(hass, [make_info(CLOSED)])
    assert _state(hass, "battery").state == "unavailable"

    async def connect(*_a, **_k):
        return _FakeClient()

    with (
        patch(f"{HUB}.async_ble_device_from_address", return_value=MagicMock()),
        patch(f"{HUB}.async_last_service_info", return_value=None),
        patch("custom_components.hacs_hunter_douglas_blind.hub.establish_connection", connect),
    ):
        await hass.services.async_call(
            "button", "press", {"entity_id": _button_id(hass)}, blocking=True
        )
    assert _state(hass, "battery").state == "63"


async def test_refresh_button_says_why_when_out_of_range(hass: HomeAssistant):
    await _setup(hass, [make_info(CLOSED)])
    with (
        patch(f"{HUB}.async_ble_device_from_address", return_value=None),
        pytest.raises(HomeAssistantError, match="no connectable Bluetooth adapter"),
    ):
        await hass.services.async_call(
            "button", "press", {"entity_id": _button_id(hass)}, blocking=True
        )


async def test_refresh_button_says_why_when_connect_fails(hass: HomeAssistant):
    from bleak.exc import BleakError

    await _setup(hass, [make_info(CLOSED)])

    async def connect(*_a, **_k):
        raise BleakError("out of slots")

    with (
        patch(f"{HUB}.async_ble_device_from_address", return_value=MagicMock()),
        patch(f"{HUB}.async_last_service_info", return_value=None),
        patch("custom_components.hacs_hunter_douglas_blind.hub.establish_connection", connect),
        pytest.raises(HomeAssistantError, match="connection failed.*out of slots"),
    ):
        await hass.services.async_call(
            "button", "press", {"entity_id": _button_id(hass)}, blocking=True
        )


async def test_refresh_button_says_why_when_no_battery(hass: HomeAssistant):
    await _setup(hass, [make_info(CLOSED)])

    class _NoBattery(_FakeClient):
        values = {}

    async def connect(*_a, **_k):
        return _NoBattery()

    with (
        patch(f"{HUB}.async_ble_device_from_address", return_value=MagicMock()),
        patch(f"{HUB}.async_last_service_info", return_value=None),
        patch("custom_components.hacs_hunter_douglas_blind.hub.establish_connection", connect),
        pytest.raises(HomeAssistantError, match="readable battery level"),
    ):
        await hass.services.async_call(
            "button", "press", {"entity_id": _button_id(hass)}, blocking=True
        )


async def test_gatt_status_reports_ok_after_a_successful_read(hass: HomeAssistant):
    entry, _cb = await _setup(hass, [make_info(CLOSED)])
    hub = entry.runtime_data

    async def connect(*_a, **_k):
        return _FakeClient()

    with (
        patch(f"{HUB}.async_ble_device_from_address", return_value=MagicMock()),
        patch(f"{HUB}.async_last_service_info", return_value=None),
        patch("custom_components.hacs_hunter_douglas_blind.hub.establish_connection", connect),
    ):
        await hub.async_poll_gatt(hub.shades["C6:83:B4:47:08:51"])
        await hass.async_block_till_done()

    assert _state(hass, "gatt_status").state == "ok"


async def test_gatt_status_reports_why_the_read_failed(hass: HomeAssistant):
    """The reason lives in state, not only in the log and the button's error."""
    from bleak.exc import BleakError

    entry, _cb = await _setup(hass, [make_info(CLOSED)])
    hub = entry.runtime_data
    shade = hub.shades["C6:83:B4:47:08:51"]

    async def connect(*_a, **_k):
        raise BleakError("ESP_GATT_ERROR")

    with (
        patch(f"{HUB}.async_ble_device_from_address", return_value=MagicMock()),
        patch(f"{HUB}.async_last_service_info", return_value=None),
        patch("custom_components.hacs_hunter_douglas_blind.hub.establish_connection", connect),
    ):
        await hub.async_poll_gatt(shade)
        await hass.async_block_till_done()

    assert "ESP_GATT_ERROR" in _state(hass, "gatt_status").state
    assert shade.last_attempt is not None


async def test_last_gatt_attempt_is_registered_but_off_by_default(hass: HomeAssistant):
    await _setup(hass, [make_info(CLOSED)])
    entity = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, "C6:83:B4:47:08:51_last_gatt_attempt"
    )
    assert entity
    assert er.async_get(hass).async_get(entity).disabled


async def test_watched_poll_gives_up_instead_of_queueing_forever(hass: HomeAssistant):
    """A press must answer even while the 6-hour sweep holds the radio."""
    entry, _cb = await _setup(hass, [make_info(CLOSED)])
    hub = entry.runtime_data
    shade = hub.shades["C6:83:B4:47:08:51"]

    before_attempt, before_error = shade.last_attempt, shade.last_error

    await hub._gatt_lock.acquire()
    try:
        failure = await hub.async_poll_gatt(shade, wait=0.01)
    finally:
        hub._gatt_lock.release()

    assert failure is not None
    assert "another shade is being read" in failure
    # A queued-out poll never reached the radio, so it is not a read failure:
    # the recorded outcome is whatever the last real attempt left behind.
    assert shade.last_attempt == before_attempt
    assert shade.last_error == before_error


async def test_retries_re_resolve_the_radio(hass: HomeAssistant):
    """Each retry asks HA for the best connectable radio again, not the first one."""
    entry, _cb = await _setup(hass, [make_info(CLOSED)])
    hub = entry.runtime_data
    first, second = MagicMock(name="proxy"), MagicMock(name="dongle")
    captured: dict = {}

    async def connect(_cls, _device, _name, **kwargs):
        captured.update(kwargs)
        return _FakeClient()

    with (
        patch(f"{HUB}.async_ble_device_from_address", side_effect=[first, second]),
        patch(f"{HUB}.async_last_service_info", return_value=None),
        patch("custom_components.hacs_hunter_douglas_blind.hub.establish_connection", connect),
    ):
        await hub.async_poll_gatt(hub.shades["C6:83:B4:47:08:51"])
        assert captured["ble_device_callback"]() is second


async def test_retries_fall_back_to_the_known_device(hass: HomeAssistant):
    """If HA has no radio to offer mid-retry, reuse the one we started with."""
    entry, _cb = await _setup(hass, [make_info(CLOSED)])
    hub = entry.runtime_data
    known = MagicMock(name="proxy")
    captured: dict = {}

    async def connect(_cls, _device, _name, **kwargs):
        captured.update(kwargs)
        return _FakeClient()

    with (
        patch(f"{HUB}.async_ble_device_from_address", side_effect=[known, None]),
        patch(f"{HUB}.async_last_service_info", return_value=None),
        patch("custom_components.hacs_hunter_douglas_blind.hub.establish_connection", connect),
    ):
        await hub.async_poll_gatt(hub.shades["C6:83:B4:47:08:51"])
        assert captured["ble_device_callback"]() is known


async def test_gatt_status_strips_control_characters(hass: HomeAssistant):
    """The failure reason becomes entity state, and a BLE error can quote the peer."""
    from bleak.exc import BleakError

    entry, _cb = await _setup(hass, [make_info(CLOSED)])
    hub = entry.runtime_data

    async def connect(*_a, **_k):
        raise BleakError("device Evil\x1b[31m\nCorp\x07 refused")

    with (
        patch(f"{HUB}.async_ble_device_from_address", return_value=MagicMock()),
        patch(f"{HUB}.async_last_service_info", return_value=None),
        patch("custom_components.hacs_hunter_douglas_blind.hub.establish_connection", connect),
    ):
        await hub.async_poll_gatt(hub.shades["C6:83:B4:47:08:51"])
        await hass.async_block_till_done()

    state = _state(hass, "gatt_status").state
    assert "Evil[31mCorp refused" in state
    assert not any(ch in state for ch in "\x1b\n\x07")


async def test_background_poll_waits_its_turn(hass: HomeAssistant):
    """Unwatched reads must queue, not give up: a shade skipped here waits 6 hours."""
    entry, _cb = await _setup(hass, [make_info(CLOSED)])
    hub = entry.runtime_data

    async def connect(*_a, **_k):
        return _FakeClient()

    await hub._gatt_lock.acquire()
    with (
        patch(f"{HUB}.async_ble_device_from_address", return_value=MagicMock()),
        patch(f"{HUB}.async_last_service_info", return_value=None),
        patch("custom_components.hacs_hunter_douglas_blind.hub.establish_connection", connect),
    ):
        task = hass.async_create_task(
            hub.async_poll_gatt(hub.shades["C6:83:B4:47:08:51"])
        )
        await asyncio.sleep(0)
        assert not task.done()  # blocked on the radio, not abandoned
        hub._gatt_lock.release()
        assert await task is None

    await hass.async_block_till_done()
    assert _state(hass, "battery").state == "63"


def test_gatt_status_is_unknown_before_any_attempt():
    """The pure function, where "never tried" is actually reachable."""
    from homeassistant.util import dt as dt_util

    from custom_components.hacs_hunter_douglas_blind.hub import ShadeData
    from custom_components.hacs_hunter_douglas_blind.protocol import parse_advertisement
    from custom_components.hacs_hunter_douglas_blind.sensor import gatt_status

    advert = parse_advertisement(bytes.fromhex(CLOSED))
    shade = ShadeData(address="C6:83:B4:47:08:51", name="PowerView", advert=advert)
    assert gatt_status(shade) is None

    shade.last_attempt = dt_util.utcnow()
    assert gatt_status(shade) == "ok"

    shade.last_error = "the connection failed"
    assert gatt_status(shade) == "the connection failed"
