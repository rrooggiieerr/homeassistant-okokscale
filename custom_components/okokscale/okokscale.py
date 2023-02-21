# This file needs to become a library once we have everything working

from __future__ import annotations

import logging

from bleak import BLEDevice, BleakClient
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from bluetooth_data_tools import short_address, human_readable_name
from bluetooth_sensor_state_data import BluetoothData
from home_assistant_bluetooth import BluetoothServiceInfo
from sensor_state_data import SensorDeviceClass, SensorUpdate, Units
from sensor_state_data.enum import StrEnum
from homeassistant.const import UnitOfMass

UPDATE_INTERVAL_SECONDS = 1

_LOGGER = logging.getLogger(__name__)


# "00002a29-0000-1000-8000-00805f9b34fb" #(Handle: 11): Manufacturer Name String
MODEL_NUMBER = "00002a24-0000-1000-8000-00805f9b34fb" #(Handle: 13): Model Number String
# "00002a25-0000-1000-8000-00805f9b34fb" #(Handle: 15): Serial Number String
# "00002a26-0000-1000-8000-00805f9b34fb" #(Handle: 17): Firmware Revision String
# "00002a27-0000-1000-8000-00805f9b34fb" #(Handle: 19): Hardware Revision String
# "0000fff1-0000-1000-8000-00805f9b34fb" #(Handle: 22): Vendor specific
# "0000fff2-0000-1000-8000-00805f9b34fb" #(Handle: 25): Vendor specific
# "00002a9c-0000-1000-8000-00805f9b34fb" #(Handle: 28): Body Composition Measurement
# "0000fa9c-0000-1000-8000-00805f9b34fb" #(Handle: 31): Vendor specific
BATTERY_LEVEL = "00002a19-0000-1000-8000-00805f9b34fb" #(Handle: 35): Battery Level
# "00002a08-0000-1000-8000-00805f9b34fb" #(Handle: 39): Date Time
# "0000faa1-0000-1000-8000-00805f9b34fb" #(Handle: 43): Vendor specific
# "0000faa2-0000-1000-8000-00805f9b34fb" #(Handle: 45): Vendor specific

MANUFACTURER_DATA_ID_V20 = 0x20ca # 16-bit little endian "header" 0xca 0x20
MANUFACTURER_DATA_ID_V11 = 0x11ca # 16-bit little endian "header" 0xca 0x11
MANUFACTURER_DATA_ID_VF0 = 0xF0FF # 16-bit little endian "header" 0xca 0x11
IDX_V20_FINAL = 6
IDX_V20_WEIGHT_MSB = 8
IDX_V20_WEIGHT_LSB = 9
IDX_V20_IMPEDANCE_MSB = 10
IDX_V20_IMPEDANCE_LSB = 11
IDX_V20_CHECKSUM = 12

IDX_V11_WEIGHT_MSB = 3;
IDX_V11_WEIGHT_LSB = 4;
IDX_V11_BODY_PROPERTIES = 9;
IDX_V11_CHECKSUM = 16;

IDX_VF0_WEIGHT_MSB = 3
IDX_VF0_WEIGHT_LSB = 2


class OKOKScaleSensor(StrEnum):
    WEIGHT = "weight"
    SIGNAL_STRENGTH = "signal_strength"
    BATTERY_PERCENT = "battery_percent"

class OKOKScaleBluetoothDeviceData(BluetoothData):
    """Data for OKOK Scale sensors."""
    name = None

    _client = None
    _expected_disconnect = False

    def __init__(self) -> None:
        super().__init__()

    def _start_update(self, service_info: BluetoothServiceInfo) -> None:
        """Update from BLE advertisement data."""
        _LOGGER.debug("Parsing OKOK Scale advertisement data: %s", service_info)

        self.set_device_manufacturer("OKOK")
        self.set_device_type("OKOK Scale")
        address = service_info.address
        _LOGGER.debug("Address: %s: ", address)
        name = f"OKOK Scale ({short_address(address)})"
        name = human_readable_name("OKOK Scale", None, address)
        self.set_device_name(name)
        self.set_title(name)

        self.process_manufacturer_data(service_info.manufacturer_data)

    def poll_needed(
        self, service_info: BluetoothServiceInfo, last_poll: float | None
    ) -> bool:
        """
        This is called every time we get a service_info for a device. It means the
        device is working and online.
        """
        _LOGGER.debug("poll_needed")
        return True
        if last_poll is None:
            return True
        return last_poll > UPDATE_INTERVAL_SECONDS

    async def connect(self, ble_device: BLEDevice):
        if self._client and self._client.is_connected:
            _LOGGER.debug("Already connected to %s", self.name)
            return self._client
        else:
            # Connecting with the scale
            self._device = ble_device
            _LOGGER.info("Connecting to %s", self.name)
            client: BleakClient = await establish_connection(
                BleakClientWithServiceCache,
                ble_device,
                self.name,
                self._disconnected,
                use_services_cache=True,
                ble_device_callback=lambda: self._device,
            )
            self._client = client

            return client

    async def disconnect(self):
        if self._client and self._client.is_connected:
            self._expected_disconnect = True
            await self._client.disconnect()

    def _disconnected(self, client: BleakClientWithServiceCache) -> None:
        """Disconnected callback."""
        if self._expected_disconnect:
            _LOGGER.debug(
                "%s: Disconnected from device",
                self.get_device_name()
            )
            return
        
        _LOGGER.warning(
            "%s: Device unexpectedly disconnected",
            self.get_device_name()
        )

    async def async_poll(self, ble_device: BLEDevice) -> SensorUpdate:
        """
        Poll the device to retrieve any values we can't get from passive listening.
        """
        try:
            client = await self.connect(ble_device)
    
            # Log characteristics for debugging
            for n in client.services.characteristics:
                try:
                    characteristic = client.services.characteristics[n]
                    gatt_char = client.services.get_characteristic(characteristic.uuid)
                    payload = await client.read_gatt_char(gatt_char)
                    _LOGGER.debug("client.services %s: %s", gatt_char, payload.decode())
                except Exception as ex:
                    if isinstance(ex, (UnicodeDecodeError)):
                        _LOGGER.debug("client.services %s: \\x%s", gatt_char, payload.hex())
    
            # Battery percentage always returns 0 on my device
            battery_char = client.services.get_characteristic(BATTERY_LEVEL)
            battery_payload = await client.read_gatt_char(battery_char)

            self.update_sensor(
                str(OKOKScaleSensor.BATTERY_PERCENT),
                Units.PERCENTAGE,
                battery_payload[0],
                SensorDeviceClass.BATTERY,
                "Battery",
            )
    
            if "manufacturer_data" in ble_device.metadata:
                manufacturer_data = ble_device.metadata["manufacturer_data"]
                self.process_manufacturer_data(manufacturer_data)
        finally:
            await self.disconnect()

        return self._finish_update()

    def process_manufacturer_data(self, manufacturer_data):
        if MANUFACTURER_DATA_ID_V20 in manufacturer_data:
            data = manufacturer_data[MANUFACTURER_DATA_ID_V20]
            _LOGGER.debug("manufacturer_data: %s", data.hex())
        elif MANUFACTURER_DATA_ID_V11 in manufacturer_data:
            data = manufacturer_data[MANUFACTURER_DATA_ID_V11]
            _LOGGER.debug("manufacturer_data: %s", data.hex())
        elif MANUFACTURER_DATA_ID_VF0 in manufacturer_data:
            data = manufacturer_data[MANUFACTURER_DATA_ID_VF0]
            _LOGGER.debug("Manufacturer Data: %s", data.hex())

            # Reading the weight
            weight = ((data[IDX_VF0_WEIGHT_MSB] << 8) + data[IDX_VF0_WEIGHT_LSB]) / 10
            _LOGGER.debug("weight: %s", weight)

            self.update_sensor(
                str(OKOKScaleSensor.WEIGHT), UnitOfMass.KILOGRAMS, weight, None, "Weight"
            )
