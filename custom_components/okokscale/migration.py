"""Migration of the OKOK Scale integration to Home Assistant Core."""

from types import MappingProxyType

from homeassistant.config_entries import SOURCE_IGNORE, ConfigEntry, ConfigEntryDisabler
from homeassistant.const import MAJOR_VERSION, MINOR_VERSION
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry, entity_registry

from .const import CORE_DOMAIN, CORE_MINOR_VERSION, CORE_SINCE, CORE_VERSION, DOMAIN


def is_supported_by_core() -> bool:
    """Return if this Home Assistant version supports OKOK Scales in Core."""
    return (MAJOR_VERSION, MINOR_VERSION) >= CORE_SINCE


@callback
def async_get_core_entry(hass: HomeAssistant, address: str) -> ConfigEntry | None:
    """Return the Core config entry for a scale, if there is one.

    An ignored entry doesn't count, Core doesn't set up the scale for it.
    """
    return next(
        (
            core_entry
            for core_entry in hass.config_entries.async_entries(
                CORE_DOMAIN, include_ignore=False
            )
            if core_entry.unique_id == address
        ),
        None,
    )


async def async_migrate_to_core(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Move a config entry, its devices and entities to the Core integration.

    A config entry can't change domain, so a new Core entry is created, the
    devices and entities are moved to it and the old entry is removed. If Core
    already has the scale, Core keeps its own devices and entities and the old
    entry is only removed.
    """
    address = entry.unique_id
    assert address is not None

    # Entities can only be moved to another integration while they aren't loaded
    if not await hass.config_entries.async_unload(entry.entry_id):
        raise HomeAssistantError(f"Unable to unload config entry {entry.title}")

    if async_get_core_entry(hass, address) is None:
        # Core may have discovered the scale already and the user ignored it
        for ignored_entry in hass.config_entries.async_entries(CORE_DOMAIN):
            if (
                ignored_entry.source == SOURCE_IGNORE
                and ignored_entry.unique_id == address
            ):
                await hass.config_entries.async_remove(ignored_entry.entry_id)
        await _async_move_to_new_core_entry(hass, entry, address)

    # Core may have discovered the scale already, with the discovery still waiting
    # for the user. Confirming it could replace the Core entry, so dismiss it.
    for flow in hass.config_entries.flow.async_progress_by_handler(
        CORE_DOMAIN, match_context={"unique_id": address}
    ):
        hass.config_entries.flow.async_abort(flow["flow_id"])

    await hass.config_entries.async_remove(entry.entry_id)


async def _async_move_to_new_core_entry(
    hass: HomeAssistant, entry: ConfigEntry, address: str
) -> None:
    """Create a Core config entry and move the devices and entities to it."""
    core_entry = ConfigEntry(
        created_at=entry.created_at,
        data=dict(entry.data),
        disabled_by=ConfigEntryDisabler.USER,
        discovery_keys=MappingProxyType({}),
        domain=CORE_DOMAIN,
        minor_version=CORE_MINOR_VERSION,
        options=dict(entry.options),
        pref_disable_new_entities=entry.pref_disable_new_entities,
        pref_disable_polling=entry.pref_disable_polling,
        source=entry.source,
        subentries_data=None,
        title=entry.title,
        unique_id=address,
        version=CORE_VERSION,
    )
    # The new entry is added disabled so it isn't set up yet. Setting it up
    # before the devices and entities are moved would make Core create new ones
    # instead of reusing the existing ones. It is enabled again below.
    await hass.config_entries.async_add(core_entry)

    ent_reg = entity_registry.async_get(hass)
    for entity in entity_registry.async_entries_for_config_entry(
        ent_reg, entry.entry_id
    ):
        if entity.platform == DOMAIN:
            ent_reg.async_update_entity_platform(
                entity.entity_id,
                CORE_DOMAIN,
                new_config_entry_id=core_entry.entry_id,
            )

    dev_reg = device_registry.async_get(hass)
    for device in device_registry.async_entries_for_config_entry(
        dev_reg, entry.entry_id
    ):
        dev_reg.async_update_device(device.id, new_config_entry_id=core_entry.entry_id)

    await hass.config_entries.async_set_disabled_by(core_entry.entry_id, None)
