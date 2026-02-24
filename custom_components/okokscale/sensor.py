"""Support for OKOK Scale sensors."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothDataUpdate,
    PassiveBluetoothProcessorCoordinator,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfMass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.sensor import sensor_device_info_to_hass_device_info

from .device import device_key_to_bluetooth_entity_key
from .okokscale import OKOKScaleSensor, SensorUpdate

SENSOR_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    OKOKScaleSensor.WEIGHT: SensorEntityDescription(
        key=OKOKScaleSensor.WEIGHT,
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key=OKOKScaleSensor.WEIGHT,
        suggested_display_precision=1,
    ),
    OKOKScaleSensor.SIGNAL_STRENGTH: SensorEntityDescription(
        key=OKOKScaleSensor.SIGNAL_STRENGTH,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        translation_key=OKOKScaleSensor.SIGNAL_STRENGTH,
    ),
    OKOKScaleSensor.BATTERY_PERCENT: SensorEntityDescription(
        key=OKOKScaleSensor.BATTERY_PERCENT,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key=OKOKScaleSensor.BATTERY_PERCENT,
    ),
    OKOKScaleSensor.IMPEDANCE: SensorEntityDescription(
        key=OKOKScaleSensor.IMPEDANCE,
        native_unit_of_measurement="Ω",
        state_class=SensorStateClass.MEASUREMENT,
        translation_key=OKOKScaleSensor.IMPEDANCE,
    ),
}


def sensor_update_to_bluetooth_data_update(
    sensor_update: SensorUpdate,
) -> PassiveBluetoothDataUpdate:
    """Convert a sensor update to a bluetooth data update."""
    entity_descriptions = {}
    for device_key in sensor_update.entity_descriptions:
        description = SENSOR_DESCRIPTIONS.get(device_key.key)
        if description is None:
            continue
        entity_descriptions[device_key_to_bluetooth_entity_key(device_key)] = description
    return PassiveBluetoothDataUpdate(
        devices={
            device_id: sensor_device_info_to_hass_device_info(device_info)
            for device_id, device_info in sensor_update.devices.items()
        },
        entity_descriptions=entity_descriptions,
        entity_data={
            device_key_to_bluetooth_entity_key(device_key): sensor_values.native_value
            for device_key, sensor_values in sensor_update.entity_values.items()
        },
        entity_names={
            device_key_to_bluetooth_entity_key(device_key): sensor_values.name
            for device_key, sensor_values in sensor_update.entity_values.items()
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the OKOK Scale sensors."""
    coordinator: PassiveBluetoothProcessorCoordinator = entry.runtime_data
    processor = PassiveBluetoothDataProcessor(sensor_update_to_bluetooth_data_update)
    entry.async_on_unload(
        processor.async_add_entities_listener(
            OKOKScaleBluetoothSensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(coordinator.async_register_processor(processor))


class OKOKScaleBluetoothSensorEntity(
    PassiveBluetoothProcessorEntity[
        PassiveBluetoothDataProcessor[str | int | None, SensorUpdate]
    ],
    SensorEntity,
):
    """Representation of an OKOK Scale sensor."""

    @property
    def native_value(self) -> str | int | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)
