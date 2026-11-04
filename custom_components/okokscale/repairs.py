"""Repairs for the OKOK Scale integration."""

import logging
from typing import override

from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .migration import async_migrate_to_core

_LOGGER = logging.getLogger(__name__)


class MigrateToCoreRepairFlow(ConfirmRepairFlow):
    """Move a scale to the Core integration once the user confirms it."""

    def __init__(self, entry_id: str) -> None:
        """Initialize the flow."""
        super().__init__()
        self._entry_id = entry_id

    @override
    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Migrate the config entry when the user confirms."""
        if user_input is None:
            return await super().async_step_confirm()

        # The entry may have been removed since the issue was created
        if entry := self.hass.config_entries.async_get_entry(self._entry_id):
            try:
                await async_migrate_to_core(self.hass, entry)
            except HomeAssistantError:
                _LOGGER.exception("Unable to move %s to Core", entry.title)
                return self.async_abort(
                    reason="migration_failed",
                    description_placeholders={"name": entry.title},
                )
        return self.async_create_entry(data={})


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create the flow that fixes an issue."""
    assert data is not None
    return MigrateToCoreRepairFlow(str(data["entry_id"]))
