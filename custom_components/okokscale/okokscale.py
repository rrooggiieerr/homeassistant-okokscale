"""
Talks to the OKOK Scale.

This file needs to become a library once we have everything working
"""

from __future__ import annotations

import logging

from bleak import AdvertisementData, BleakClient, BLEDevice
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from bluetooth_data_tools import human_readable_name
from bluetooth_sensor_state_data import BluetoothData
from home_assistant_bluetooth import BluetoothServiceInfo
from homeassistant.const import UnitOfMass
from sensor_state_data import SensorDeviceClass, SensorUpdate, Units
from sensor_state_data.enum import StrEnum

UPDATE_INTERVAL_SECONDS = 1

_LOGGER = logging.getLogger(__name__)


# "00002a29-0000-1000-8000-00805f9b34fb" #(Handle: 11): Manufacturer Name String
CHARACTERISTIC_MODEL_NUMBER = (
    "00002a24-0000-1000-8000-00805f9b34fb"  # (Handle: 13): Model Number String
)
# "00002a25-0000-1000-8000-00805f9b34fb" #(Handle: 15): Serial Number String
# "00002a26-0000-1000-8000-00805f9b34fb" #(Handle: 17): Firmware Revision String
# "00002a27-0000-1000-8000-00805f9b34fb" #(Handle: 19): Hardware Revision String
# "0000fff1-0000-1000-8000-00805f9b34fb" #(Handle: 22): Vendor specific
# "0000fff2-0000-1000-8000-00805f9b34fb" #(Handle: 25): Vendor specific
# "00002a9c-0000-1000-8000-00805f9b34fb" #(Handle: 28): Body Composition Measurement
# "0000fa9c-0000-1000-8000-00805f9b34fb" #(Handle: 31): Vendor specific
CHARACTERISTIC_BATTERY_LEVEL = (
    "00002a19-0000-1000-8000-00805f9b34fb"  # (Handle: 35): Battery Level
)
# "00002a08-0000-1000-8000-00805f9b34fb" #(Handle: 39): Date Time
# "0000faa1-0000-1000-8000-00805f9b34fb" #(Handle: 43): Vendor specific
# "0000faa2-0000-1000-8000-00805f9b34fb" #(Handle: 45): Vendor specific

MANUFACTURER_DATA_ID_V10 = 0x10FF  # 16-bit little endian "header" 0xff 0x10
MANUFACTURER_DATA_ID_V11 = 0x11CA  # 16-bit little endian "header" 0xca 0x11
MANUFACTURER_DATA_ID_V20 = 0x20CA  # 16-bit little endian "header" 0xca 0x20
MANUFACTURER_DATA_ID_V26 = 0x26C0  # 16-bit little endian "header" 0xc0 0x26
MANUFACTURER_DATA_ID_VC0 = 0xC0  # 8-bit little endian "header" 0xc0
MANUFACTURER_DATA_ID_VF0 = 0xF0FF  # 16-bit little endian "header" 0xff 0xf0

IDX_V10_WEIGHT_MSB = 3
IDX_V10_WEIGHT_LSB = 2

IDX_V11_WEIGHT_MSB = 3
IDX_V11_WEIGHT_LSB = 4
IDX_V11_BODY_PROPERTIES = 9
IDX_V11_CHECKSUM = 16

IDX_V20_FINAL = 6
IDX_V20_WEIGHT_MSB = 8
IDX_V20_WEIGHT_LSB = 9
IDX_V20_IMPEDANCE_MSB = 10
IDX_V20_IMPEDANCE_LSB = 11
IDX_V20_CHECKSUM = 12

IDX_V26_WEIGHT_MSB = 3
IDX_V26_WEIGHT_LSB = 2

IDX_VC0_FINAL = 6
IDX_VC0_WEIGHT_MSB = 0
IDX_VC0_WEIGHT_LSB = 1
IDX_VC0_BODY_PROPERTIES = 6

IDX_VF0_WEIGHT_MSB = 3
IDX_VF0_WEIGHT_LSB = 2

LB_TO_KG = 0.45359237


class OKOKScaleSensor(StrEnum):
    # pylint: disable=too-few-public-methods
    """The different sensors de OKOK Scale provides."""

    WEIGHT = "weight"
    IMPEDANCE = "impedance"
    SIGNAL_STRENGTH = "signal_strength"
    BATTERY_PERCENT = "battery_percent"


class OKOKScaleBluetoothDeviceData(BluetoothData):
    """Data for OKOK Scale sensors."""

    name = None

    _device = None
    _client = None
    _expected_disconnect = False

    def _start_update(self, service_info: BluetoothServiceInfo) -> None:
        """Update from BLE advertisement data."""
        if not (
            service_info.name in ["ADV", "Chipsea-BLE"]
            or service_info.name.startswith("Yoda0")
            or service_info.name.startswith("Yoda1")
            or service_info.name.startswith("80:F4:16:")
        ):
            return

        manufacturer_data_key_lsbs = [
            key & 0xFF for key in service_info.manufacturer_data
        ]
        if not (
            MANUFACTURER_DATA_ID_V10 in service_info.manufacturer_data
            or MANUFACTURER_DATA_ID_V11 in service_info.manufacturer_data
            or MANUFACTURER_DATA_ID_V20 in service_info.manufacturer_data
            or MANUFACTURER_DATA_ID_V26 in service_info.manufacturer_data
            or MANUFACTURER_DATA_ID_VC0 in manufacturer_data_key_lsbs
            or MANUFACTURER_DATA_ID_VF0 in service_info.manufacturer_data
        ):
            _LOGGER.debug(
                "Manufacturer data not found for %s; ids=%s",
                service_info.address,
                list(service_info.manufacturer_data.keys()),
            )
            return

        self.log_service_info(service_info)

        self.set_device_manufacturer("OKOK")
        self.set_device_type("OKOK Scale")
        address = service_info.address
        _LOGGER.debug("Address: %s: ", address)
        name = human_readable_name(
            "OKOK Scale", service_info.name, service_info.address
        )
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
        # if last_poll is None:
        #     return True
        # return last_poll > UPDATE_INTERVAL_SECONDS

    async def connect(self, ble_device: BLEDevice):
        if self._client and self._client.is_connected:
            _LOGGER.debug("Already connected to %s", self.name)
            return self._client

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
            _LOGGER.debug("%s: Disconnected from device", self.get_device_name())
            return

        _LOGGER.warning("%s: Device unexpectedly disconnected", self.get_device_name())

    async def async_poll(
        self, ble_device: BLEDevice, advertisement_data: AdvertisementData
    ) -> SensorUpdate:
        """
        Poll the device to retrieve any values we can't get from passive listening.
        """
        try:
            client = await self.connect(ble_device)
            await self.log_client(client)

            # Trying to figure out how this body composition payload works
            body_composition_char = client.services.get_characteristic(
                "00002a9c-0000-1000-8000-00805f9b34fb"
            )
            body_composition_payload = await client.read_gatt_char(
                body_composition_char
            )
            _LOGGER.debug(
                "body_composition_payload: 0x%s", body_composition_payload.hex()
            )
            _LOGGER.debug(
                "body_composition_payload: %s %s",
                hex(body_composition_payload[11]),
                body_composition_payload[11],
            )

            # Battery percentage always returns 0 on my device
            battery_char = client.services.get_characteristic(
                CHARACTERISTIC_BATTERY_LEVEL
            )
            battery_payload = await client.read_gatt_char(battery_char)

            self.update_sensor(
                OKOKScaleSensor.BATTERY_PERCENT,
                Units.PERCENTAGE,
                battery_payload[0],
                SensorDeviceClass.BATTERY,
                "Battery",
            )

            self.process_manufacturer_data(advertisement_data.manufacturer_data)
        finally:
            await self.disconnect()

        return self._finish_update()

    def process_manufacturer_data(self, manufacturer_data):
        if MANUFACTURER_DATA_ID_V10 in manufacturer_data:
            data = manufacturer_data[MANUFACTURER_DATA_ID_V10]
            _LOGGER.debug("manufacturer_data: %s", data.hex())
            return
        if MANUFACTURER_DATA_ID_V26 in manufacturer_data:
            data = manufacturer_data[MANUFACTURER_DATA_ID_V26]
            _LOGGER.debug("manufacturer_data: %s", data.hex())
            return

        (
            self._process_manufacturer_data_v11(manufacturer_data)
            or self._process_manufacturer_data_v20(manufacturer_data)
            or self._process_manufacturer_data_vc0(manufacturer_data)
            or self._process_manufacturer_data_vf0(manufacturer_data)
        )

    def _process_manufacturer_data_v11(self, manufacturer_data):
        if MANUFACTURER_DATA_ID_V11 not in manufacturer_data:
            return False

        data = manufacturer_data[MANUFACTURER_DATA_ID_V11]
        _LOGGER.debug("manufacturer_data: %s", data.hex())
        if data is None or len(data) != IDX_V11_CHECKSUM + 6 + 1:
            return False

        checksum = (
            0xCA ^ 0x11
        )  # Version and magic fields are part of the checksum, but not in array
        for i in range(0, IDX_V11_CHECKSUM - 1):
            checksum ^= data[i]
        if data[IDX_V11_CHECKSUM] != checksum:
            _LOGGER.error(
                "Checksum error, got %s, expected %s",
                hex(data[IDX_V11_CHECKSUM] & 0xFF),
                hex(checksum & 0xFF),
            )
            return False

        # Reading the weight
        divider = 10.0
        weight = data[IDX_V11_WEIGHT_MSB] & 0xFF
        weight = weight << 8 | (data[IDX_V11_WEIGHT_LSB] & 0xFF)

        match (data[IDX_V11_BODY_PROPERTIES] >> 1) & 3:
            case 0:
                divider = 10.0
            case 1:
                divider = 1.0
            case 2:
                divider = 100.0
            case _:
                _LOGGER.warning("Invalid weight scale received, assuming 1 decimal")
                divider = 10.0

        unit_of_measurement = None
        match (data[IDX_V11_BODY_PROPERTIES] >> 3) & 3:
            case 0:  # kg
                weight = weight / divider
                unit_of_measurement = UnitOfMass.KILOGRAMS
            case 1:  # Jin
                divider *= 2.0
                weight = weight / divider
                unit_of_measurement = UnitOfMass.KILOGRAMS
            case 3:  # st & lb
                stones = weight >> 8
                pounds = (weight & 0xFF) / divider
                weight = pounds + (stones * 14)
                unit_of_measurement = UnitOfMass.POUNDS
            case 2:  # lb
                weight = weight / divider
                unit_of_measurement = UnitOfMass.POUNDS
        _LOGGER.debug("weight: %f", weight)

        self.update_sensor(
            OKOKScaleSensor.WEIGHT,
            unit_of_measurement,
            weight,
            None,
            "Weight",
        )

        return True

    def _process_manufacturer_data_v20(self, manufacturer_data):
        if MANUFACTURER_DATA_ID_V20 not in manufacturer_data:
            return False

        data = manufacturer_data[MANUFACTURER_DATA_ID_V20]
        _LOGGER.debug("manufacturer_data: %s", data.hex())
        if data is None or len(data) != 19:
            return False

        if (data[IDX_V20_FINAL] & 1) == 0:
            _LOGGER.debug(
                "Data is not final, got %s, expected 0x00",
                hex(data[IDX_V20_FINAL] & 1),
            )
            return False

        checksum = 0x20  # Version field is part of the checksum, but not in array
        for i in range(0, IDX_V20_CHECKSUM - 1):
            checksum ^= data[i]
        if data[IDX_V20_CHECKSUM] != checksum:
            _LOGGER.error(
                "Checksum error, got %s, expected %s",
                hex(data[IDX_V20_CHECKSUM] & 0xFF),
                hex(checksum & 0xFF),
            )
            return False

        # Reading the weight
        divider = 10.0
        if (data[IDX_V20_FINAL] & 4) == 4:
            divider = 100.0
        weight = ((data[IDX_V20_WEIGHT_MSB] << 8) + data[IDX_V20_WEIGHT_LSB]) / divider
        _LOGGER.debug("weight: %f", weight)

        # Reading the impedance
        impedance = (data[IDX_V20_IMPEDANCE_MSB] << 8) + data[
            IDX_V20_IMPEDANCE_LSB
        ] / 10.0

        self.update_sensor(
            OKOKScaleSensor.WEIGHT, UnitOfMass.KILOGRAMS, weight, None, "Weight"
        )

        self.update_sensor(OKOKScaleSensor.IMPEDANCE, "Ω", impedance, None, "Impedance")

        return True

    def _process_manufacturer_data_vc0(self, manufacturer_data):
        data = None
        stable_data = None
        for key in manufacturer_data:
            # Run through the whole list of values so we get the final reading
            if (key & 0xFF) != MANUFACTURER_DATA_ID_VC0:
                continue
            # Discard 0 readings - we seem to get a lot of them
            _data = manufacturer_data[key]
            if _data[IDX_VC0_WEIGHT_MSB] == 0 and _data[IDX_VC0_WEIGHT_LSB] == 0:
                continue
            data = _data
            if (data[IDX_VC0_FINAL] & 1) == 1:
                stable_data = data

        if data is None:
            return False

        # Prefer readings marked as final, but settle for the latest non-zero
        if stable_data is not None:
            data = stable_data

        msb = data[IDX_VC0_WEIGHT_MSB]
        lsb = data[IDX_VC0_WEIGHT_LSB]
        _LOGGER.debug("manufacturer_data: %s", data.hex())
        match data[IDX_VC0_BODY_PROPERTIES] >> 3 & 0x3:
            case 0:  # kg
                weight = weight_kg = (msb << 8 | lsb) / 100.0
                # unit_of_measurement = UnitOfMass.KILOGRAMS
            case 2:  # lb
                weight = (msb << 8 | lsb) / 10.0
                weight_kg = weight * LB_TO_KG
                # unit_of_measurement = UnitOfMass.POUNDS
            case 3:  # st:lb
                weight = msb * 14 + lsb / 10.0
                weight_kg = weight * LB_TO_KG
                # unit_of_measurement = UnitOfMass.POUNDS
        _LOGGER.debug("weight: %f", weight)
        self.update_sensor(
            OKOKScaleSensor.WEIGHT,
            UnitOfMass.KILOGRAMS,
            weight_kg,
            None,
            "Weight",
        )
        return True

    def _process_manufacturer_data_vf0(self, manufacturer_data):
        if MANUFACTURER_DATA_ID_VF0 not in manufacturer_data:
            return False

        data = manufacturer_data[MANUFACTURER_DATA_ID_VF0]
        if len(data) != 18:
            return False

        _LOGGER.debug("Manufacturer Data: %s", data.hex())

        # Reading the weight
        # ToDo use unpack
        weight = ((data[IDX_VF0_WEIGHT_MSB] << 8) + data[IDX_VF0_WEIGHT_LSB]) / 10.0
        _LOGGER.debug("weight: %f", weight)

        self.update_sensor(
            OKOKScaleSensor.WEIGHT, UnitOfMass.KILOGRAMS, weight, None, "Weight"
        )
        return True

    def log_service_info(self, service_info: BluetoothServiceInfo):
        if not _LOGGER.isEnabledFor(logging.DEBUG):
            return

        _LOGGER.debug("device name: %s", service_info.name)
        _LOGGER.debug("device address: %s", service_info.address)
        _LOGGER.debug("device rssi: %s", service_info.rssi)

        manufacturer_data = service_info.manufacturer_data
        for manufacturer_id in manufacturer_data:
            data = manufacturer_data[manufacturer_id]
            _LOGGER.debug("manufacturer identifier: %s", hex(manufacturer_id))
            _LOGGER.debug("manufacturer data length: %s", len(data))
            try:
                _LOGGER.debug("manufacturer data: %s", data.decode())
                _LOGGER.debug("manufacturer data: 0x%s", data.hex())
            except UnicodeDecodeError:
                _LOGGER.debug("manufacturer data: 0x%s", data.hex())
            except Exception:
                pass

        service_data = service_info.service_data
        for service_id in service_data:
            try:
                data = service_data[service_id]
                _LOGGER.debug("service data %s: %s", service_id, data.decode())
                _LOGGER.debug("service data %s: 0x%s", service_id, data.hex())
            except UnicodeDecodeError:
                _LOGGER.debug("service data %s: 0x%s", service_id, data.hex())
            except Exception:
                pass

        _LOGGER.debug("service uuids: %s", service_info.service_uuids)
        _LOGGER.debug("device source: %s", service_info.source)

    async def log_client(self, client):
        if not _LOGGER.isEnabledFor(logging.DEBUG):
            return

        # Log characteristics for debugging
        for i in client.services.characteristics:
            try:
                characteristic = client.services.characteristics[i]
                gatt_char = client.services.get_characteristic(characteristic.uuid)
                payload = await client.read_gatt_char(gatt_char)
                _LOGGER.debug("client.services %s: %s", gatt_char, payload.decode())
                _LOGGER.debug("client.services %s: 0x%s", gatt_char, payload.hex())
            except Exception as ex:
                if isinstance(ex, (UnicodeDecodeError)):
                    _LOGGER.debug("client.services %s: 0x%s", gatt_char, payload.hex())
