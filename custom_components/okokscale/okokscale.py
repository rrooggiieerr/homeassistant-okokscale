# This file needs to become a library once we have everything working

from __future__ import annotations

import logging

from bleak import BLEDevice, BleakClient
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from bluetooth_data_tools import short_address
from bluetooth_sensor_state_data import BluetoothData
from home_assistant_bluetooth import BluetoothServiceInfo
from sensor_state_data import SensorDeviceClass, SensorUpdate, Units
from sensor_state_data.enum import StrEnum
from bleak.backends.corebluetooth.characteristic import BleakGATTCharacteristicCoreBluetooth

UPDATE_INTERVAL_SECONDS = 5

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
# "00002a19-0000-1000-8000-00805f9b34fb" #(Handle: 35): Battery Level
# "00002a08-0000-1000-8000-00805f9b34fb" #(Handle: 39): Date Time
# "0000faa1-0000-1000-8000-00805f9b34fb" #(Handle: 43): Vendor specific
# "0000faa2-0000-1000-8000-00805f9b34fb" #(Handle: 45): Vendor specific


class OKOKScaleSensor(StrEnum):
    WEIGHT = "weight"
    SIGNAL_STRENGTH = "signal_strength"
    BATTERY_PERCENT = "battery_percent"

class OKOKScaleBluetoothDeviceData(BluetoothData):
    """Data for OKOK Scale sensors."""

    def __init__(self) -> None:
        super().__init__()
        # If this is True, we are currently brushing or were brushing as of the last advertisement data
        self._brushing = False
        self._last_brush = 0.0

    def _start_update(self, service_info: BluetoothServiceInfo) -> None:
        """Update from BLE advertisement data."""
        _LOGGER.debug("Parsing OKOK Scale advertisement data: %s", service_info)
        manufacturer_data = service_info.manufacturer_data
        _LOGGER.debug("manufacturer_data: %s", manufacturer_data)
        address = service_info.address
        self.set_device_manufacturer("OKOK")

        self.set_device_type("OKOK Scale")
        name = f"OKOK Scale ({short_address(address)})"
        self.set_device_name(name)
        self.set_title(name)

        weight = 0
        #ToDo reading the scale goes here
        
        self.update_sensor(
            str(OKOKScaleSensor.WEIGHT), None, weight, None, "Weight"
        )

    def poll_needed(
        self, service_info: BluetoothServiceInfo, last_poll: float | None
    ) -> bool:
        """
        This is called every time we get a service_info for a device. It means the
        device is working and online.
        """
        if last_poll is None:
            return True
        return last_poll > UPDATE_INTERVAL_SECONDS

    async def async_poll(self, ble_device: BLEDevice) -> SensorUpdate:
        """
        Poll the device to retrieve any values we can't get from passive listening.
        """
        client: BleakClient = await establish_connection(
            BleakClientWithServiceCache, ble_device, ble_device.address
        )
        try:
            # Printing the characteristics for debugging purposes
            for n in client.services.characteristics:
                characteristic: BleakGATTCharacteristicCoreBluetooth = client.services.characteristics[n]
                gatt_char = client.services.get_characteristic(characteristic.uuid)
                try:
                    payload = await client.read_gatt_char(gatt_char)
                    _LOGGER.debug("client.services %s: %s", gatt_char, payload)
                except Exception:
                    pass
            
            # Battery percentage always returns 0 on my device
            battery_char = client.services.get_characteristic("00002a19-0000-1000-8000-00805f9b34fb")
            battery_payload = await client.read_gatt_char(battery_char)
        finally:
            await client.disconnect()
        self.update_sensor(
            str(OKOKScaleSensor.BATTERY_PERCENT),
            Units.PERCENTAGE,
            battery_payload[0],
            SensorDeviceClass.BATTERY,
            "Battery",
        )
        return self._finish_update()