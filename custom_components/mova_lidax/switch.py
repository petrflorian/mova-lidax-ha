"""Switch entities for MOVA LiDAX schedules."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MAX_SCHEDULE_SLOTS
from .coordinator import MovaLidaxCoordinator
from .entity import MovaLidaxEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: MovaLidaxCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[MovaLidaxEntity] = []
    for map_item in coordinator.extra_attributes.get("maps") or []:
        map_id = map_item.get("map_id")
        map_name = map_item.get("name") or f"Map {map_id}"
        if map_id is None:
            continue
        for schedule_id in range(MAX_SCHEDULE_SLOTS):
            entities.append(MovaLidaxScheduleEnabledSwitch(coordinator, map_id, map_name, schedule_id))
            for weekday in range(7):
                entities.append(MovaLidaxScheduleWeekdaySwitch(coordinator, map_id, map_name, schedule_id, weekday))
    async_add_entities(entities)


class MovaLidaxScheduleEnabledSwitch(MovaLidaxEntity, SwitchEntity):
    """Enable/disable a known LiDAX schedule slot."""

    _attr_icon = "mdi:calendar-check"

    def __init__(self, coordinator: MovaLidaxCoordinator, map_id: int, map_name: str, schedule_id: int) -> None:
        super().__init__(coordinator)
        self._map_id = map_id
        self._map_name = map_name
        self._schedule_id = schedule_id
        self._attr_name = f"{map_name} Schedule {schedule_id} Enabled"

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_map_{self._map_id}_schedule_{self._schedule_id}_enabled"

    @property
    def is_on(self) -> bool | None:
        entry = self.coordinator.get_schedule_entry(self._map_id, self._schedule_id)
        if entry is None:
            return None
        return bool(entry.get("enabled"))

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
            "time": entry.get("time"),
            "weekday_names": entry.get("weekday_names"),
            "zones": entry.get("zones"),
            "zone_names": entry.get("zone_names"),
        }

    async def async_turn_on(self, **kwargs) -> None:
        await self._exec(self.coordinator.update_schedule_entry, self._map_id, self._schedule_id, enabled=True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._exec(self.coordinator.update_schedule_entry, self._map_id, self._schedule_id, enabled=False)


class MovaLidaxScheduleWeekdaySwitch(MovaLidaxEntity, SwitchEntity):
    """Toggle a weekday for a known LiDAX schedule slot."""

    _attr_icon = "mdi:calendar-week"
    _DAY_NAMES = {
        0: "Mon",
        1: "Tue",
        2: "Wed",
        3: "Thu",
        4: "Fri",
        5: "Sat",
        6: "Sun",
    }

    def __init__(
        self,
        coordinator: MovaLidaxCoordinator,
        map_id: int,
        map_name: str,
        schedule_id: int,
        weekday: int,
    ) -> None:
        super().__init__(coordinator)
        self._map_id = map_id
        self._map_name = map_name
        self._schedule_id = schedule_id
        self._weekday = weekday
        self._attr_name = f"{map_name} Schedule {schedule_id} {self._DAY_NAMES.get(weekday, weekday)}"

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_map_{self._map_id}_schedule_{self._schedule_id}_weekday_{self._weekday}"

    @property
    def available(self) -> bool:
        return self.coordinator.get_schedule_entry(self._map_id, self._schedule_id) is not None

    @property
    def is_on(self) -> bool | None:
        entry = self.coordinator.get_schedule_entry(self._map_id, self._schedule_id)
        if entry is None:
            return None
        return self._weekday in (entry.get("weekdays") or [])

    @property
    def extra_state_attributes(self):
        entry = self.coordinator.get_schedule_entry(self._map_id, self._schedule_id)
        if entry is None:
            return None
        return {
            "map_id": self._map_id,
            "map_name": self._map_name,
            "schedule_id": self._schedule_id,
            "weekday": self._weekday,
            "time": entry.get("time"),
            "weekday_names": entry.get("weekday_names"),
            "zones": entry.get("zones"),
            "zone_names": entry.get("zone_names"),
        }

    async def async_turn_on(self, **kwargs) -> None:
        entry = self.coordinator.get_schedule_entry(self._map_id, self._schedule_id)
        weekdays = sorted(set((entry.get("weekdays") or []) + [self._weekday])) if entry else [self._weekday]
        await self._exec(
            self.coordinator.update_schedule_entry,
            self._map_id,
            self._schedule_id,
            weekdays=weekdays,
        )

    async def async_turn_off(self, **kwargs) -> None:
        entry = self.coordinator.get_schedule_entry(self._map_id, self._schedule_id)
        weekdays = [day for day in (entry.get("weekdays") or []) if day != self._weekday] if entry else []
        await self._exec(
            self.coordinator.update_schedule_entry,
            self._map_id,
            self._schedule_id,
            weekdays=weekdays,
        )
