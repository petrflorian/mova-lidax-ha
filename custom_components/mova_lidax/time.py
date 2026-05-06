"""Time entities for MOVA LiDAX schedules."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MAX_SCHEDULE_SLOTS
from .coordinator import MovaLidaxCoordinator
from .entity import MovaLidaxEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: MovaLidaxCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[MovaLidaxScheduleTimeEntity] = []
    for map_item in coordinator.extra_attributes.get("maps") or []:
        map_id = map_item.get("map_id")
        map_name = map_item.get("name") or f"Map {map_id}"
        if map_id is None:
            continue
        for schedule_id in range(MAX_SCHEDULE_SLOTS):
            entities.append(MovaLidaxScheduleTimeEntity(coordinator, map_id, map_name, schedule_id))
    async_add_entities(entities)


class MovaLidaxScheduleTimeEntity(MovaLidaxEntity, TimeEntity):
    """Edit time of a known LiDAX schedule slot."""

    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator: MovaLidaxCoordinator, map_id: int, map_name: str, schedule_id: int) -> None:
        super().__init__(coordinator)
        self._map_id = map_id
        self._map_name = map_name
        self._schedule_id = schedule_id
        self._attr_name = f"{map_name} Schedule {schedule_id} Time"

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_map_{self._map_id}_schedule_{self._schedule_id}_time"

    @property
    def native_value(self) -> time | None:
        entry = self.coordinator.get_schedule_entry(self._map_id, self._schedule_id)
        minutes = entry.get("time_minutes") if entry else None
        if not isinstance(minutes, int):
            return None
        hours, mins = divmod(minutes, 60)
        return time(hour=hours % 24, minute=mins)

    @property
    def available(self) -> bool:
        return self.coordinator.get_schedule_entry(self._map_id, self._schedule_id) is not None

    @property
    def extra_state_attributes(self):
        entry = self.coordinator.get_schedule_entry(self._map_id, self._schedule_id)
        if entry is None:
            return None
        return {
            "map_id": self._map_id,
            "map_name": self._map_name,
            "schedule_id": self._schedule_id,
            "enabled": entry.get("enabled"),
            "weekday_names": entry.get("weekday_names"),
            "zones": entry.get("zones"),
            "zone_names": entry.get("zone_names"),
        }

    async def async_set_value(self, value: time) -> None:
        await self._exec(
            self.coordinator.update_schedule_entry,
            self._map_id,
            self._schedule_id,
            time_minutes=value.hour * 60 + value.minute,
        )
