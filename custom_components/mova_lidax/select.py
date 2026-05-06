"""Select entities for MOVA LiDAX."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_MAP_ID, ATTR_MAP_INDEX, DOMAIN
from .coordinator import MovaLidaxCoordinator
from .entity import MovaLidaxEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: MovaLidaxCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MovaLidaxSelectedMapEntity(coordinator)])


class MovaLidaxSelectedMapEntity(MovaLidaxEntity, SelectEntity):
    """Selected map entity."""

    _attr_translation_key = "selected_map"
    _attr_icon = "mdi:map-check"
    _attr_name = "Selected Map"

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_selected_map"

    @property
    def current_option(self) -> str | None:
        selected_map = self.device.status.selected_map
        return selected_map.map_name if selected_map else None

    @property
    def options(self) -> list[str]:
        return [map_data.map_name for map_data in self.device.status.map_data_list.values()]

    @property
    def extra_state_attributes(self):
        selected_map = self.device.status.selected_map
        maps = [
            {
                "map_id": map_id,
                "map_index": map_data.map_index,
                "name": map_data.map_name,
            }
            for map_id, map_data in self.device.status.map_data_list.items()
        ]
        attrs = {"maps": maps}
        if selected_map:
            attrs[ATTR_MAP_ID] = selected_map.map_id
            attrs[ATTR_MAP_INDEX] = selected_map.map_index
        return attrs

    async def async_select_option(self, option: str) -> None:
        map_id = next(
            (map_id for map_id, map_data in self.device.status.map_data_list.items() if map_data.map_name == option),
            None,
        )
        if map_id is not None:
            await self._exec(self.device.set_selected_map, map_id)
