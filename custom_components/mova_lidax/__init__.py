"""MOVA LiDAX integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError

from .const import ATTR_MAP_ID, DOMAIN, SERVICE_SWITCH_MAP
from .coordinator import MovaLidaxCoordinator

PLATFORMS = (
    Platform.LAWN_MOWER,
    Platform.SENSOR,
    Platform.SELECT,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MOVA LiDAX from a config entry."""
    coordinator = MovaLidaxCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    async def async_switch_map_service(call: ServiceCall) -> None:
        map_id = call.data.get(ATTR_MAP_ID)
        if not isinstance(map_id, int):
            raise HomeAssistantError("map_id is required")

        coordinators: dict[str, MovaLidaxCoordinator] = hass.data.get(DOMAIN, {})
        if not coordinators:
            raise HomeAssistantError("No MOVA LiDAX device is available")

        coordinator = next(iter(coordinators.values()))
        await hass.async_add_executor_job(coordinator.device.set_selected_map, map_id)
        coordinator.async_set_updated_data(coordinator.device)

    if not hass.services.has_service(DOMAIN, SERVICE_SWITCH_MAP):
        hass.services.async_register(DOMAIN, SERVICE_SWITCH_MAP, async_switch_map_service)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: MovaLidaxCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator.device.listen(None)
        coordinator.device.disconnect()
        if not hass.data[DOMAIN] and hass.services.has_service(DOMAIN, SERVICE_SWITCH_MAP):
            hass.services.async_remove(DOMAIN, SERVICE_SWITCH_MAP)
    return unload_ok
