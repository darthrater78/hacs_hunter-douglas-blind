"""Fixtures for the Home Assistant side of the integration (pytest only)."""

from __future__ import annotations

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from bleak.backends.device import BLEDevice  # noqa: E402
from bleak.backends.scanner import AdvertisementData  # noqa: E402
from habluetooth import BluetoothServiceInfoBleak  # noqa: E402

MANUFACTURER_ID = 0x0819
ADDRESS = "C6:83:B4:47:08:51"


def make_info(payload_hex: str, address: str = ADDRESS, rssi: int = -67):
    """Build the service info Home Assistant would hand us for one advertisement."""
    device = BLEDevice(address, "PowerView", {})
    adv = AdvertisementData(
        local_name="PowerView",
        manufacturer_data={MANUFACTURER_ID: bytes.fromhex(payload_hex)},
        service_data={},
        service_uuids=[],
        rssi=rssi,
        tx_power=None,
        platform_data=(),
    )
    return BluetoothServiceInfoBleak.from_device_and_advertisement_data(
        device, adv, "local", True, 0.0
    )


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations):
    yield
