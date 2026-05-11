"""MOVA LiDAX integration."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import async_register_built_in_panel, async_remove_panel
from homeassistant.components.http import StaticPathConfig
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
    Platform.CAMERA,
)

PANEL_URL_PATH = "mova-lidax"
PANEL_STATIC_URL = "/mova_lidax_static/panel.js"


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

    await _async_register_panel(hass)
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
        if not hass.data[DOMAIN]:
            async_remove_panel(hass, PANEL_URL_PATH)
    return unload_ok


async def _async_register_panel(hass: HomeAssistant) -> None:
    """Register the built-in MOVA LiDAX dashboard panel."""
    frontend_dir = Path(__file__).parent / "frontend"
    await hass.http.async_register_static_paths(
        [StaticPathConfig("/mova_lidax_static", str(frontend_dir), cache_headers=False)]
    )
    async_remove_panel(hass, PANEL_URL_PATH)
    async_register_built_in_panel(
        hass,
        component_name="custom",
        sidebar_title="MOVA LiDAX",
        sidebar_icon="mdi:robot-mower",
        frontend_url_path=PANEL_URL_PATH,
        config={
            "_panel_custom": {
                "name": "mova-lidax-panel",
                "embed_iframe": True,
                "trust_external": False,
                "js_url": PANEL_STATIC_URL,
            }
        },
        require_admin=False,
    )
