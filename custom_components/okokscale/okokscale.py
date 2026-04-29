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
from sensor_state_data import SensorDeviceClass, SensorLibrary, SensorUpdate, Units

UPDATE_INTERVAL_SECONDS = 60 * 60 * 24  # 1 day

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
CHARACTERISTIC_BODY_COMPOSITION = (
    "00002a9c-0000-1000-8000-00805f9b34fb"  # (Handle: 28): Body Composition Measurement
)
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

IDX_V11_FINAL = 1
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


class OKOKScaleBluetoothDeviceData(BluetoothData):
    """Data for OKOK Scale sensors."""

    name = None

    _device = None
    _client = None
    _expected_disconnect = False

    supports_impedance = False

    def _start_update(self, service_info: BluetoothServiceInfo) -> None:
        """Update from BLE advertisement data."""
        if _LOGGER.isEnabledFor(logging.DEBUG):
            self.log_service_info(service_info)

        manufacturer_data_key_lsbs = [
            key & 0xFF for key in service_info.manufacturer_data
        ]
        if not (
            MANUFACTURER_DATA_ID_V10 in service_info.manufacturer_data
            or MANUFACTURER_DATA_ID_V11 in service_info.manufacturer_data
            or MANUFACTURER_DATA_ID_V20 in service_info.manufacturer_data
            or MANUFACTURER_DATA_ID_V26 in service_info.manufacturer_data
            or MANUFACTURER_DATA_ID_VF0 in service_info.manufacturer_data
            or MANUFACTURER_DATA_ID_VC0 in manufacturer_data_key_lsbs
        ):
            _LOGGER.info(
                "Manufacturer data not found for %s; ids=%s",
                service_info.address,
                list(service_info.manufacturer_data.keys()),
            )
            return

        self.set_device_manufacturer("OKOK")
        self.set_device_type("OKOK Scale")
        name = human_readable_name(
            "OKOK Scale", service_info.name, service_info.address
        )
        self.set_device_name(name)
        self.set_title(name)

        self.process_manufacturer_data(service_info.manufacturer_data)

        self.update_signal_strength(service_info.rssi)

    def poll_needed(
        self, service_info: BluetoothServiceInfo, last_poll: float | None
    ) -> bool:
        """
        This is called every time we get a service_info for a device. It means the
        device is working and online.
        """
        if last_poll is None or self.supports_impedance:
            return True
        return last_poll > UPDATE_INTERVAL_SECONDS

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
            if _LOGGER.isEnabledFor(logging.DEBUG):
                await self.log_client(client)

            body_composition_char = client.services.get_characteristic(
                CHARACTERISTIC_BODY_COMPOSITION
            )
            if body_composition_char:
                self.supports_impedance = True

                body_composition_payload = await client.read_gatt_char(
                    body_composition_char
                )
                _LOGGER.debug(
                    "Body Composition Payload: 0x%s", body_composition_payload.hex()
                )

                control_bytes = (
                    body_composition_payload[1] << 8
                ) + body_composition_payload[0]
                partial = (control_bytes & 1024) > 0
                in_pounds = (control_bytes & 256) > 0
                finished = (control_bytes & 128) > 0
                in_jin = (control_bytes & 64) > 0
                weight_stabilized = (control_bytes & 32) > 0
                impedance_stabilized = (control_bytes & 2) > 0

                weight = (
                    (body_composition_payload[12] << 8) + body_composition_payload[11]
                ) / 10
                _LOGGER.debug("Weight: %.2f kg", weight)

                impedance = (
                    body_composition_payload[10] << 8
                ) + body_composition_payload[9]
                _LOGGER.debug("Impedance: %d Ω", impedance)

                self.update_predefined_sensor(
                    SensorLibrary.MASS__MASS_KILOGRAMS, weight, "weight"
                )

                self.update_predefined_sensor(SensorLibrary.IMPEDANCE__OHM, impedance)

            # Battery percentage always returns 0 on my device
            battery_char = client.services.get_characteristic(
                CHARACTERISTIC_BATTERY_LEVEL
            )
            if battery_char:
                battery_payload = await client.read_gatt_char(battery_char)

                self.update_predefined_sensor(
                    SensorLibrary.BATTERY__PERCENTAGE,
                    battery_payload[0],
                )

            self.log_manufacturer_data(advertisement_data.manufacturer_data)
            self.process_manufacturer_data(advertisement_data.manufacturer_data)
        finally:
            await self.disconnect()

        return self._finish_update()

    def process_manufacturer_data(self, manufacturer_data):
        if MANUFACTURER_DATA_ID_V10 in manufacturer_data:
            return
        if MANUFACTURER_DATA_ID_V26 in manufacturer_data:
            return

        if MANUFACTURER_DATA_ID_V11 in manufacturer_data:
            self._process_manufacturer_data_v11(manufacturer_data)
        elif MANUFACTURER_DATA_ID_V20 in manufacturer_data:
            self._process_manufacturer_data_v20(manufacturer_data)
        elif MANUFACTURER_DATA_ID_VF0 in manufacturer_data:
            self._process_manufacturer_data_vf0(manufacturer_data)
        else:
            self._process_manufacturer_data_vc0(manufacturer_data)

    def _process_manufacturer_data_v11(self, manufacturer_data):
        data = manufacturer_data[MANUFACTURER_DATA_ID_V11]
        if data is None or len(data) != IDX_V11_CHECKSUM + 6 + 1:
            _LOGGER.error(
                "Data length error, got %d, expected %d",
                len(data),
                IDX_V11_CHECKSUM + 6 + 1,
            )
            return

        if (data[IDX_V11_FINAL] & 1) == 0:
            _LOGGER.debug("Data is not final")
            return

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
            return

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

        base_description = None
        match (data[IDX_V11_BODY_PROPERTIES] >> 3) & 3:
            case 0:  # kg
                weight = weight / divider
                base_description = SensorLibrary.MASS__MASS_KILOGRAMS
            case 1:  # Jin
                divider *= 2.0
                weight = weight / divider
                base_description = SensorLibrary.MASS__MASS_KILOGRAMS
            case 2:  # lb
                weight = weight / divider
                base_description = SensorLibrary.MASS__MASS_POUNDS
            case 3:  # st & lb
                stones = weight >> 8
                pounds = (weight & 0xFF) / divider
                weight = pounds + (stones * 14)
                base_description = SensorLibrary.MASS__MASS_POUNDS
        _LOGGER.debug(
            "Weight: %.2f %s", weight, base_description.native_unit_of_measurement
        )

        self.update_predefined_sensor(base_description, weight, "weight")

    def _process_manufacturer_data_v20(self, manufacturer_data):
        data = manufacturer_data[MANUFACTURER_DATA_ID_V20]
        if data is None or len(data) != 19:
            _LOGGER.error("Data length error, got %d, expected 19", len(data))
            return

        if (data[IDX_V20_FINAL] & 1) == 0:
            _LOGGER.debug("Data is not final")
            return

        checksum = 0x20  # Version field is part of the checksum, but not in array
        for i in range(0, IDX_V20_CHECKSUM - 1):
            checksum ^= data[i]
        if data[IDX_V20_CHECKSUM] != checksum:
            _LOGGER.error(
                "Checksum error, got 0x%s, expected 0x%s",
                hex(data[IDX_V20_CHECKSUM] & 0xFF),
                hex(checksum & 0xFF),
            )
            return

        # Reading the weight
        divider = 10.0
        if (data[IDX_V20_FINAL] & 4) == 4:
            divider = 100.0
        weight = ((data[IDX_V20_WEIGHT_MSB] << 8) + data[IDX_V20_WEIGHT_LSB]) / divider
        _LOGGER.debug("Weight: %.2f kg", weight)

        # Reading the impedance
        impedance = (
            (data[IDX_V20_IMPEDANCE_MSB] << 8) + data[IDX_V20_IMPEDANCE_LSB]
        ) / 10.0
        _LOGGER.debug("Impedance: %.1f Ω", impedance)

        self.update_predefined_sensor(
            SensorLibrary.MASS__MASS_KILOGRAMS, weight, "weight"
        )

        self.update_predefined_sensor(SensorLibrary.IMPEDANCE__OHM, impedance)

    def _process_manufacturer_data_vc0(self, manufacturer_data):
        data = None
        final = False
        for key, _data in manufacturer_data.items():
            # Run through the whole list of values so we get the final reading
            if (key & 0xFF) != MANUFACTURER_DATA_ID_VC0:
                continue
            if len(_data) != 13:
                continue
            if _data[IDX_VC0_WEIGHT_MSB] == 0 and _data[IDX_VC0_WEIGHT_LSB] == 0:
                continue

            if (data[IDX_VC0_FINAL] & 1) != 0:
                data = _data
            elif not final:
                data = _data

        if data is None:
            return

        if not final:
            _LOGGER.debug("Data is not final")
            # return

        msb = data[IDX_VC0_WEIGHT_MSB]
        lsb = data[IDX_VC0_WEIGHT_LSB]
        base_description = None
        match data[IDX_VC0_BODY_PROPERTIES] >> 3 & 0x3:
            case 0:  # kg
                weight = (msb << 8 | lsb) / 100.0
                base_description = SensorLibrary.MASS__MASS_KILOGRAMS
            case 2:  # lb
                weight = (msb << 8 | lsb) / 10.0
                base_description = SensorLibrary.MASS__MASS_POUNDS
            case 3:  # st:lb
                weight = msb * 14 + lsb / 10.0
                base_description = SensorLibrary.MASS__MASS_POUNDS
        _LOGGER.debug(
            "Weight: %.2f %s", weight, base_description.native_unit_of_measurement
        )

        self.update_predefined_sensor(base_description, weight, "weight")

    def _process_manufacturer_data_vf0(self, manufacturer_data):
        data = manufacturer_data[MANUFACTURER_DATA_ID_VF0]
        if len(data) != 18:
            _LOGGER.error("Data length error, got %d, expected 18", len(data))
            return

        # Reading the weight
        # ToDo use unpack
        weight = ((data[IDX_VF0_WEIGHT_MSB] << 8) + data[IDX_VF0_WEIGHT_LSB]) / 10.0
        _LOGGER.debug("Weight: %.1f kg", weight)

        self.update_predefined_sensor(
            SensorLibrary.MASS__MASS_KILOGRAMS, weight, "weight"
        )

    def log_service_info(self, service_info: BluetoothServiceInfo):
        _LOGGER.debug("Device Name: %s", service_info.name)
        _LOGGER.debug("Device Address: %s", service_info.address)
        _LOGGER.debug("Device RSSI: %s", service_info.rssi)

        self.log_manufacturer_data(service_info.manufacturer_data)

        service_data = service_info.service_data
        for service_id in service_data:
            try:
                data = service_data[service_id]
                _LOGGER.debug("Service Data %s: %s", service_id, data.decode())
                _LOGGER.debug("Service Data %s: 0x%s", service_id, data.hex())
            except UnicodeDecodeError:
                _LOGGER.debug("Service Data %s: 0x%s", service_id, data.hex())
            except Exception:
                pass

        _LOGGER.debug("Service UUIDs: %s", service_info.service_uuids)

    def log_manufacturer_data(self, manufacturer_data):
        for manufacturer_id in manufacturer_data:
            data = manufacturer_data[manufacturer_id]
            _LOGGER.debug("Manufacturer Identifier: %s", hex(manufacturer_id))
            _LOGGER.debug("Manufacturer Data Length: %s", len(data))
            try:
                _LOGGER.debug("Manufacturer Data: %s", data.decode())
                _LOGGER.debug("Manufacturer Data: 0x%s", data.hex())
            except UnicodeDecodeError:
                _LOGGER.debug("Manufacturer Data: 0x%s", data.hex())
            except Exception:
                pass

    async def log_client(self, client):
        # Log characteristics for debugging
        for i in client.services.characteristics:
            try:
                characteristic = client.services.characteristics[i]
                gatt_char = client.services.get_characteristic(characteristic.uuid)
                payload = await client.read_gatt_char(gatt_char)
                _LOGGER.debug("client.services %s: %s", gatt_char, payload.decode())
                _LOGGER.debug("client.services %s: 0x%s", gatt_char, payload.hex())
            except UnicodeDecodeError:
                _LOGGER.debug("client.services %s: 0x%s", gatt_char, payload.hex())
            except Exception:
                pass
