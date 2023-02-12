"""The OKOK Scale integration."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OKOK Scale from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    
    return True
