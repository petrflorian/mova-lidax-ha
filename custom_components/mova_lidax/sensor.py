"""Sensors for MOVA LiDAX."""

from __future__ import annotations

from datetime import datetime, timedelta
from html import escape

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, ENABLE_DEBUG_SNAPSHOT
from .coordinator import MovaLidaxCoordinator
from .entity import MovaLidaxEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: MovaLidaxCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            MovaLidaxBatterySensor(coordinator),
            MovaLidaxStateSensor(coordinator),
            MovaLidaxTaskStatusSensor(coordinator),
            MovaLidaxActiveMapSensor(coordinator),
            MovaLidaxMapHintSensor(coordinator),
            MovaLidaxCloudOnlineSensor(coordinator),
            MovaLidaxCloudStatusSensor(coordinator),
            MovaLidaxCloudUpdatedAtSensor(coordinator),
            MovaLidaxCloudVideoStatusSensor(coordinator),
            MovaLidaxFirmwareSensor(coordinator),
            MovaLidaxDndSensor(coordinator),
            MovaLidaxDndStartSensor(coordinator),
            MovaLidaxDndEndSensor(coordinator),
            MovaLidaxSavedMapsSensor(coordinator),
            MovaLidaxMapNamesSensor(coordinator),
            MovaLidaxTotalSchedulesSensor(coordinator),
            MovaLidaxRuntimeMowedAreaSensor(coordinator),
            MovaLidaxRuntimeTargetAreaSensor(coordinator),
            MovaLidaxRuntimeProgressSensor(coordinator),
            MovaLidaxCurrentPositionXSensor(coordinator),
            MovaLidaxCurrentPositionYSensor(coordinator),
            MovaLidaxPositionSourceSensor(coordinator),
            MovaLidaxCurrentMapAreaSensor(coordinator),
            MovaLidaxCurrentMapZonesSensor(coordinator),
            MovaLidaxCurrentMapSchedulesSensor(coordinator),
            MovaLidaxCurrentMapGeometrySensor(coordinator),
            MovaLidaxCurrentMapScheduleSlotSensor(coordinator, 0),
            MovaLidaxCurrentMapScheduleSlotSensor(coordinator, 1),
            MovaLidaxCurrentMapScheduleSlotSensor(coordinator, 2),
            MovaLidaxAiObstacleSensor(coordinator),
            MovaLidaxCurrentPathAvoidObsSensor(coordinator),
            MovaLidaxRuntimeLayersSensor(coordinator),
            MovaLidaxOtaInfoSensor(coordinator),
            MovaLidaxLastCleaningTimeSensor(coordinator),
            MovaLidaxLastCleaningAreaSensor(coordinator),
            MovaLidaxLastCleaningDurationSensor(coordinator),
            MovaLidaxLastMowingMapSensor(coordinator),
            MovaLidaxLastMowingCompletionSensor(coordinator),
            MovaLidaxTotalMowedAreaSensor(coordinator),
            MovaLidaxWeeklyMowingSummarySensor(coordinator),
            MovaLidaxCleaningHistorySensor(coordinator),
        ]
    )


class _BaseSensor(MovaLidaxEntity, SensorEntity):
    _attr_name = None


class _RestoredRuntimeSensor(_BaseSensor, RestoreEntity):
    """Runtime values can disappear while LiDAX is paused/DND; keep the last useful value."""

    _last_runtime_value: float | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._last_runtime_value = _coerce_number(last_state.state)

    def _runtime_value(self, key: str) -> float | None:
        runtime = _lidax_runtime_packet(self.device)
        value = _coerce_number(runtime.get(key)) if runtime else None
        if value is not None:
            self._last_runtime_value = value
            return value
        return self._last_runtime_value


class MovaLidaxBatterySensor(_BaseSensor):
    _attr_translation_key = "battery"
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:battery"
    _attr_name = "Battery"

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_battery"

    @property
    def native_value(self):
        return self.device.status.battery_level

    @property
    def extra_state_attributes(self):
        summary = self.coordinator.extra_attributes.get("cloud_summary") or {}
        return {"cloud_summary": summary} if summary else None


class MovaLidaxStateSensor(_BaseSensor):
    _attr_translation_key = "state"
    _attr_icon = "mdi:robot-mower"
    _attr_name = "State"

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_state"

    @property
    def native_value(self):
        return self.device.status.state_name


class MovaLidaxTaskStatusSensor(_BaseSensor):
    _attr_icon = "mdi:message-text-clock-outline"
    _attr_name = "Task Status"

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_task_status"

    @property
    def native_value(self):
        dnd_settings = self.coordinator.extra_attributes.get("dnd_settings") or {}
        if _is_dnd_active(dnd_settings):
            return "DND is on. Task paused."
        return self.device.status.state_name

    @property
    def extra_state_attributes(self):
        dnd_settings = self.coordinator.extra_attributes.get("dnd_settings") or {}
        return {
            "dnd_enabled": dnd_settings.get("enabled"),
            "dnd_active": _is_dnd_active(dnd_settings),
            "dnd_start": dnd_settings.get("start"),
            "dnd_end": dnd_settings.get("end"),
            "mower_state": self.device.status.state_name,
        }


class MovaLidaxActiveMapSensor(_BaseSensor):
    _attr_translation_key = "active_map_ha"
    _attr_icon = "mdi:map-check"
    _attr_name = "Active Map (HA)"

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_active_map_ha"

    @property
    def native_value(self):
        selected_map = self.device.status.selected_map
        return selected_map.map_name if selected_map else None


class MovaLidaxMapHintSensor(_BaseSensor):
    _attr_icon = "mdi:map-marker-question"
    _attr_name = "Map Hint"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_map_hint"

    @property
    def native_value(self):
        selected_map = self.device.status.selected_map
        if selected_map and selected_map.map_name:
            return selected_map.map_name
        return getattr(self.device, "_batch_selected_map_name", None)


class MovaLidaxCloudOnlineSensor(_BaseSensor):
    _attr_translation_key = "cloud_online"
    _attr_icon = "mdi:cloud-check-outline"
    _attr_name = "Cloud Online"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_cloud_online"

    @property
    def native_value(self):
        summary = self.coordinator.extra_attributes.get("cloud_summary") or {}
        online = summary.get("online")
        if online is None:
            return None
        return "on" if online else "off"

    @property
    def extra_state_attributes(self):
        summary = self.coordinator.extra_attributes.get("cloud_summary") or {}
        return summary or None


class MovaLidaxCloudStatusSensor(_BaseSensor):
    _attr_translation_key = "cloud_status"
    _attr_icon = "mdi:cloud-question"
    _attr_name = "Cloud Status"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_cloud_status"

    @property
    def native_value(self):
        summary = self.coordinator.extra_attributes.get("cloud_summary") or {}
        code = summary.get("latest_status")
        return f"status_{code}" if code is not None else None

    @property
    def extra_state_attributes(self):
        summary = self.coordinator.extra_attributes.get("cloud_summary") or {}
        if not summary:
            return None
        return {
            "latest_status": summary.get("latest_status"),
            "update_time": summary.get("update_time"),
            "device_status": summary.get("device_status"),
        }


class MovaLidaxCloudUpdatedAtSensor(_BaseSensor):
    _attr_translation_key = "cloud_last_update"
    _attr_icon = "mdi:cloud-clock-outline"
    _attr_name = "Cloud Last Update"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_cloud_last_update"

    @property
    def native_value(self):
        summary = self.coordinator.extra_attributes.get("cloud_summary") or {}
        return summary.get("update_time")


class MovaLidaxCloudVideoStatusSensor(_BaseSensor):
    _attr_translation_key = "cloud_video_status"
    _attr_icon = "mdi:video-wireless-outline"
    _attr_name = "Cloud Video Status"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_cloud_video_status"

    @property
    def native_value(self):
        summary = self.coordinator.extra_attributes.get("cloud_summary") or {}
        return summary.get("video_status")


class MovaLidaxFirmwareSensor(_BaseSensor):
    _attr_translation_key = "firmware_version"
    _attr_icon = "mdi:chip"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_name = "Firmware Version"

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_firmware"

    @property
    def native_value(self):
        return self.device.info.version if self.device.info else None


class MovaLidaxDndSensor(_BaseSensor):
    _attr_icon = "mdi:minus-circle-outline"
    _attr_name = "Do Not Disturb"

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_dnd"

    @property
    def native_value(self):
        dnd_settings = self.coordinator.extra_attributes.get("dnd_settings") or {}
        dnd = dnd_settings.get("enabled")
        if dnd is None:
            dnd = self.device.status.dnd
        if dnd is None:
            return None
        return "on" if dnd else "off"

    @property
    def extra_state_attributes(self):
        dnd_settings = self.coordinator.extra_attributes.get("dnd_settings") or {}
        return {
            "start": dnd_settings.get("start") or self.device.status.dnd_start,
            "end": dnd_settings.get("end") or self.device.status.dnd_end,
            "tasks": dnd_settings.get("tasks") or self.device.status.dnd_tasks,
            "remaining_seconds": self.device.status.dnd_remaining,
            "raw_properties": dnd_settings.get("raw_properties"),
        }


class MovaLidaxDndStartSensor(_BaseSensor):
    _attr_icon = "mdi:clock-start"
    _attr_name = "Do Not Disturb Start"

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_dnd_start"

    @property
    def native_value(self):
        dnd_settings = self.coordinator.extra_attributes.get("dnd_settings") or {}
        return dnd_settings.get("start") or self.device.status.dnd_start


class MovaLidaxDndEndSensor(_BaseSensor):
    _attr_icon = "mdi:clock-end"
    _attr_name = "Do Not Disturb End"

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_dnd_end"

    @property
    def native_value(self):
        dnd_settings = self.coordinator.extra_attributes.get("dnd_settings") or {}
        return dnd_settings.get("end") or self.device.status.dnd_end


class MovaLidaxSavedMapsSensor(_BaseSensor):
    _attr_icon = "mdi:map-multiple"
    _attr_name = "Saved Maps"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_saved_maps"

    @property
    def native_value(self):
        maps = self.coordinator.extra_attributes.get("maps") or []
        return len(maps)

    @property
    def extra_state_attributes(self):
        maps = self.coordinator.extra_attributes.get("maps") or []
        return {"maps": maps} if maps else None


class MovaLidaxMapNamesSensor(_BaseSensor):
    _attr_icon = "mdi:format-list-bulleted"
    _attr_name = "Map Names"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_map_names"

    @property
    def native_value(self):
        names = [item.get("name") for item in (self.coordinator.extra_attributes.get("maps") or []) if item.get("name")]
        return ", ".join(names) if names else None

    @property
    def extra_state_attributes(self):
        maps = self.coordinator.extra_attributes.get("maps") or []
        if not maps:
            return None
        return {
            "names": [item.get("name") for item in maps if item.get("name")],
            "map_indexes": [item.get("map_index") for item in maps],
        }


class MovaLidaxTotalSchedulesSensor(_BaseSensor):
    _attr_icon = "mdi:calendar-multiple"
    _attr_name = "Total Schedules"

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_total_schedules"

    @property
    def native_value(self):
        schedules = self.coordinator.extra_attributes.get("schedules") or []
        return sum(len(item.get("entries") or []) for item in schedules)

    @property
    def extra_state_attributes(self):
        schedules = self.coordinator.extra_attributes.get("schedules") or []
        if not schedules:
            return None
        return {
            "by_map": {
                (item.get("map_name") or f'Map {item.get("map_index")}'): len(item.get("entries") or [])
                for item in schedules
            }
        }


class MovaLidaxRuntimeMowedAreaSensor(_RestoredRuntimeSensor):
    _attr_icon = "mdi:mower"
    _attr_name = "Current Mowed Area"
    _attr_native_unit_of_measurement = "m²"

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_runtime_mowed_area"

    @property
    def native_value(self):
        value = self._runtime_value("mowed_area")
        return value if value is not None else 0


class MovaLidaxRuntimeTargetAreaSensor(_RestoredRuntimeSensor):
    _attr_icon = "mdi:texture-box"
    _attr_name = "Current Mowing Target Area"
    _attr_native_unit_of_measurement = "m²"

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_runtime_target_area"

    @property
    def native_value(self):
        value = self._runtime_value("mowing_target_area")
        if value is not None:
            return value
        return _current_map_total_area(self.coordinator, self.device)


class MovaLidaxRuntimeProgressSensor(_RestoredRuntimeSensor):
    _attr_icon = "mdi:progress-check"
    _attr_name = "Current Mowing Progress"
    _attr_native_unit_of_measurement = "%"

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_runtime_progress"

    @property
    def native_value(self):
        value = self._runtime_value("mowing_progress")
        if value is not None:
            return max(0, min(100, value))

        runtime = _lidax_runtime_packet(self.device)
        mowed_area = _coerce_number(runtime.get("mowed_area"))
        target_area = _coerce_number(runtime.get("mowing_target_area"))
        if mowed_area is not None and target_area:
            return round(max(0, min(100, (mowed_area / target_area) * 100)), 2)
        return 0


class MovaLidaxCurrentPositionXSensor(_BaseSensor):
    _attr_icon = "mdi:axis-x-arrow"
    _attr_name = "Current Position X"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_current_position_x"

    @property
    def native_value(self):
        runtime = _resolve_global_runtime_positions(self.coordinator, self.device)
        position = runtime.get("current_position")
        return round(float(position["x"]), 1) if isinstance(position, dict) and isinstance(position.get("x"), (int, float)) else None


class MovaLidaxCurrentPositionYSensor(_BaseSensor):
    _attr_icon = "mdi:axis-y-arrow"
    _attr_name = "Current Position Y"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_current_position_y"

    @property
    def native_value(self):
        runtime = _resolve_global_runtime_positions(self.coordinator, self.device)
        position = runtime.get("current_position")
        return round(float(position["y"]), 1) if isinstance(position, dict) and isinstance(position.get("y"), (int, float)) else None


class MovaLidaxPositionSourceSensor(_BaseSensor):
    _attr_icon = "mdi:crosshairs-question"
    _attr_name = "Position Source"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_position_source"

    @property
    def native_value(self):
        runtime = _resolve_global_runtime_positions(self.coordinator, self.device)
        return runtime.get("position_source")


class MovaLidaxCurrentMapAreaSensor(_BaseSensor):
    _attr_icon = "mdi:texture-box"
    _attr_name = "Current Map Area"
    _attr_native_unit_of_measurement = "m²"

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_current_map_area"

    @property
    def native_value(self):
        current_map = self._current_map_info
        return current_map.get("total_area") if current_map else None

    @property
    def extra_state_attributes(self):
        current_map = self._current_map_info
        if not current_map:
            return None
        runtime_positions = _resolve_runtime_positions(
            self.coordinator,
            self.device,
            current_map,
            self.coordinator.extra_attributes.get("maps") or [],
        )
        return {
            "map_name": current_map.get("name"),
            "map_index": current_map.get("map_index"),
            "cloud_summary": self.coordinator.extra_attributes.get("cloud_summary"),
            "boundary": current_map.get("boundary"),
            "zones": current_map.get("zones"),
            "paths": current_map.get("paths"),
            "contours": current_map.get("contours"),
            "current_position": runtime_positions.get("current_position"),
            "charger_position": runtime_positions.get("charger_position"),
            "position_source": runtime_positions.get("position_source"),
            "position_note": "Raw diagnostic coordinates only. Not yet mapped reliably to the selected saved map.",
            "svg": _build_map_svg(current_map, {}, self.coordinator.extra_attributes.get("maps") or []),
        }

    @property
    def _current_map_info(self):
        selected_map = self.device.status.selected_map
        maps = self.coordinator.extra_attributes.get("maps") or []
        if not selected_map:
            return None
        for item in maps:
            if item.get("map_id") == selected_map.map_id:
                return item
            if item.get("name") == selected_map.map_name:
                return item
            if item.get("map_index") == selected_map.map_index:
                return item
        return None


class MovaLidaxCurrentMapZonesSensor(_BaseSensor):
    _attr_icon = "mdi:view-grid-outline"
    _attr_name = "Current Map Zones"

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_current_map_zones"

    @property
    def native_value(self):
        current_map = self._current_map_info
        return current_map.get("zone_count") if current_map else None

    @property
    def extra_state_attributes(self):
        current_map = self._current_map_info
        return {"zones": current_map.get("zones")} if current_map else None

    @property
    def _current_map_info(self):
        selected_map = self.device.status.selected_map
        maps = self.coordinator.extra_attributes.get("maps") or []
        if not selected_map:
            return None
        for item in maps:
            if item.get("map_id") == selected_map.map_id:
                return item
            if item.get("name") == selected_map.map_name:
                return item
            if item.get("map_index") == selected_map.map_index:
                return item
        return None


class MovaLidaxCurrentMapSchedulesSensor(_BaseSensor):
    _attr_icon = "mdi:calendar-clock"
    _attr_name = "Current Map Schedules"

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_current_map_schedules"

    @property
    def native_value(self):
        schedule = self._current_schedule
        return len(schedule.get("entries", [])) if schedule else 0

    @property
    def extra_state_attributes(self):
        schedule = self._current_schedule
        if not schedule:
            return None
        return {
            "map_id": schedule.get("map_id"),
            "map_index": schedule.get("map_index"),
            "map_name": schedule.get("map_name"),
            "entries": schedule.get("entries", []),
            "skipped_entries": len(schedule.get("skipped_entries") or []),
            "skipped_raw_entries": schedule.get("skipped_entries", []),
        }

    @property
    def _current_schedule(self):
        selected_map = self.device.status.selected_map
        schedules = self.coordinator.extra_attributes.get("schedules") or []
        if not selected_map:
            return None
        for item in schedules:
            if item.get("map_id") == selected_map.map_id:
                return item
            if item.get("map_index") == selected_map.map_index:
                return item
        return None


class MovaLidaxCurrentMapGeometrySensor(_BaseSensor):
    _attr_icon = "mdi:vector-polygon"
    _attr_name = "Current Map Geometry"

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_current_map_geometry"

    @property
    def native_value(self):
        current_map = self._current_map_info
        if not current_map:
            return None
        zone_count = len(current_map.get("zones") or [])
        contour_count = len(current_map.get("contours") or [])
        return f"{zone_count} zones / {contour_count} contours"

    @property
    def extra_state_attributes(self):
        current_map = self._current_map_info
        if not current_map:
            return None
        return {
            "map_name": current_map.get("name"),
            "map_index": current_map.get("map_index"),
            "boundary": current_map.get("boundary"),
            "zones": current_map.get("zones"),
            "paths": current_map.get("paths"),
            "contours": current_map.get("contours"),
        }

    @property
    def _current_map_info(self):
        selected_map = self.device.status.selected_map
        maps = self.coordinator.extra_attributes.get("maps") or []
        if not selected_map:
            return None
        for item in maps:
            if item.get("map_id") == selected_map.map_id:
                return item
            if item.get("name") == selected_map.map_name:
                return item
            if item.get("map_index") == selected_map.map_index:
                return item
        return None


class MovaLidaxCurrentMapScheduleSlotSensor(_BaseSensor):
    _attr_icon = "mdi:calendar-text"

    def __init__(self, coordinator: MovaLidaxCoordinator, slot: int) -> None:
        super().__init__(coordinator)
        self._slot = slot
        self._attr_name = f"Current Map Schedule {slot}"

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_current_map_schedule_{self._slot}"

    @property
    def native_value(self):
        entry = self._entry
        if not entry:
            return "Unavailable"
        status = "On" if entry.get("enabled") else "Off"
        time_value = entry.get("time") or "--:--"
        days = ", ".join(entry.get("weekday_names") or [])
        if days:
            return f"{status} {time_value} ({days})"
        return f"{status} {time_value}"

    @property
    def available(self) -> bool:
        return self._entry is not None

    @property
    def extra_state_attributes(self):
        entry = self._entry
        if not entry:
            return None
        return {
            "schedule_id": entry.get("schedule_id"),
            "job_id": entry.get("job_id"),
            "enabled": entry.get("enabled"),
            "time": entry.get("time"),
            "time_minutes": entry.get("time_minutes"),
            "weekday_names": entry.get("weekday_names"),
            "zones": entry.get("zones"),
            "zone_names": entry.get("zone_names"),
            "mode": entry.get("mode"),
            "visibility_flag": entry.get("visibility_flag"),
        }

    @property
    def _entry(self):
        selected_map = self.device.status.selected_map
        schedules = self.coordinator.extra_attributes.get("schedules") or []
        if not selected_map:
            return None
        for item in schedules:
            if item.get("map_id") == selected_map.map_id or item.get("map_index") == selected_map.map_index:
                entries = item.get("entries") or []
                if self._slot < len(entries):
                    return entries[self._slot]
        return None


class MovaLidaxAiObstacleSensor(_BaseSensor):
    _attr_icon = "mdi:robot-confused-outline"
    _attr_name = "AI Obstacle Detection"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_ai_obstacle_detection"

    @property
    def native_value(self):
        value = self.coordinator.extra_attributes.get("ai_obstacle_detection")
        if isinstance(value, bool):
            return "on" if value else "off"
        return value


class MovaLidaxCurrentPathAvoidObsSensor(_BaseSensor):
    _attr_icon = "mdi:map-marker-path"
    _attr_name = "Current Path Avoid Obstacles"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_current_path_avoid_obstacles"

    @property
    def native_value(self):
        path = self._current_path
        return path.get("avoid_obstacles") if path else None

    @property
    def extra_state_attributes(self):
        path = self._current_path
        return {"settings": path.get("settings")} if path else None

    @property
    def _current_path(self):
        selected_map = self.device.status.selected_map
        paths = self.coordinator.extra_attributes.get("path") or []
        if not selected_map:
            return None
        for item in paths:
            if item.get("map_id") == selected_map.map_id:
                return item
            if item.get("map_index") == selected_map.map_index:
                return item
        return None


class MovaLidaxRuntimeLayersSensor(_BaseSensor):
    _attr_icon = "mdi:layers-search-outline"
    _attr_name = "Runtime Layers"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_runtime_layers"

    @property
    def native_value(self):
        keys = [
            key
            for key in ("fbd_ntype", "taskid", "moving_streams", "raw_position")
            if key in self.coordinator.extra_attributes
        ]
        return ", ".join(keys) if keys else None

    @property
    def extra_state_attributes(self):
        attrs = {}
        for key in ("fbd_ntype", "taskid", "raw_position"):
            if key in self.coordinator.extra_attributes:
                attrs[key] = self.coordinator.extra_attributes[key]
        streams = _summarize_streams(self.coordinator.extra_attributes.get("moving_streams"))
        if streams:
            attrs["moving_stream_count"] = len(streams)
            attrs["moving_streams_summary"] = streams
        if ENABLE_DEBUG_SNAPSHOT:
            attrs["debug_snapshot"] = "/local/mova-lidax-debug.json"
        return attrs or None


def _summarize_streams(streams):
    if not isinstance(streams, list):
        return []
    summaries = []
    for stream in streams[:16]:
        if not isinstance(stream, dict):
            continue
        points = stream.get("points") or []
        if not isinstance(points, list):
            continue
        summaries.append(
            {
                "map_id": stream.get("map_id"),
                "map_index": stream.get("map_index"),
                "point_count": len(points),
                "first": points[0] if points else None,
                "last": points[-1] if points else None,
                "bounds": _point_bounds(points),
            }
        )
    return summaries


def _point_bounds(points):
    xy = [
        (point.get("x"), point.get("y"))
        for point in points
        if isinstance(point, dict)
        and isinstance(point.get("x"), (int, float))
        and isinstance(point.get("y"), (int, float))
    ]
    if not xy:
        return None
    xs = [item[0] for item in xy]
    ys = [item[1] for item in xy]
    return {"x1": min(xs), "y1": min(ys), "x2": max(xs), "y2": max(ys)}


class MovaLidaxOtaInfoSensor(_BaseSensor):
    _attr_icon = "mdi:update"
    _attr_name = "OTA Info"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_ota_info"

    @property
    def native_value(self):
        ota = self.coordinator.extra_attributes.get("ota_info")
        if isinstance(ota, list):
            return ",".join(str(item) for item in ota)
        return ota

    @property
    def extra_state_attributes(self):
        ota = self.coordinator.extra_attributes.get("ota_info")
        if isinstance(ota, list):
            return {"values": ota}
        return None


class MovaLidaxLastCleaningTimeSensor(_BaseSensor):
    _attr_icon = "mdi:history"
    _attr_name = "Last Mowing Time"

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_last_cleaning_time"

    @property
    def native_value(self):
        entry = _latest_mowing_entry(self.coordinator)
        if entry:
            return entry.get("created_at") or entry.get("start_time")
        value = self.device.status.last_cleaning_time
        return value.isoformat() if isinstance(value, datetime) else None

    @property
    def extra_state_attributes(self):
        entry = _latest_mowing_entry(self.coordinator) or _latest_cleaning_entry(self.device)
        return entry if entry else None


class MovaLidaxLastCleaningAreaSensor(_BaseSensor):
    _attr_icon = "mdi:mower"
    _attr_name = "Last Mowing Area"
    _attr_native_unit_of_measurement = "m²"

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_last_cleaning_area"

    @property
    def native_value(self):
        entry = _latest_mowing_entry(self.coordinator)
        if entry:
            return entry.get("mowed_area")
        entry = _latest_cleaning_entry(self.device)
        return _parse_prefixed_number(entry.get("cleaned_area") if isinstance(entry, dict) else None)

    @property
    def extra_state_attributes(self):
        entry = _latest_mowing_entry(self.coordinator) or _latest_cleaning_entry(self.device)
        return entry if entry else None


class MovaLidaxLastCleaningDurationSensor(_BaseSensor):
    _attr_icon = "mdi:timer-outline"
    _attr_name = "Last Mowing Duration"
    _attr_native_unit_of_measurement = "min"

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_last_cleaning_duration"

    @property
    def native_value(self):
        entry = _latest_mowing_entry(self.coordinator)
        if entry:
            return entry.get("duration")
        entry = _latest_cleaning_entry(self.device)
        return _parse_prefixed_number(entry.get("cleaning_time") if isinstance(entry, dict) else None)

    @property
    def extra_state_attributes(self):
        entry = _latest_mowing_entry(self.coordinator) or _latest_cleaning_entry(self.device)
        return entry if entry else None


class MovaLidaxLastMowingMapSensor(_BaseSensor):
    _attr_icon = "mdi:map-marker-check"
    _attr_name = "Last Mowing Map"

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_last_mowing_map"

    @property
    def native_value(self):
        entry = _latest_mowing_entry(self.coordinator)
        return entry.get("map_name") if entry else None

    @property
    def extra_state_attributes(self):
        entry = _latest_mowing_entry(self.coordinator)
        return entry if entry else None


class MovaLidaxLastMowingCompletionSensor(_BaseSensor):
    _attr_icon = "mdi:progress-check"
    _attr_name = "Last Mowing Completion"
    _attr_native_unit_of_measurement = "%"

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_last_mowing_completion"

    @property
    def native_value(self):
        entry = _latest_mowing_entry(self.coordinator)
        return entry.get("completion_percent") if entry else None


class MovaLidaxTotalMowedAreaSensor(_BaseSensor):
    _attr_icon = "mdi:sigma"
    _attr_name = "Total Mowed Area"
    _attr_native_unit_of_measurement = "m²"

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_total_mowed_area"

    @property
    def native_value(self):
        history = _mowing_history(self.coordinator)
        values = [entry.get("mowed_area") for entry in history if isinstance(entry.get("mowed_area"), (int, float))]
        return round(sum(values), 2) if values else None

    @property
    def extra_state_attributes(self):
        history = _mowing_history(self.coordinator)
        if not history:
            return None
        by_map: dict[str, float] = {}
        for entry in history:
            area = entry.get("mowed_area")
            if not isinstance(area, (int, float)):
                continue
            map_name = entry.get("map_name") or "Unknown"
            by_map[map_name] = round(by_map.get(map_name, 0) + area, 2)
        return {"runs": len(history), "by_map": by_map}


class MovaLidaxWeeklyMowingSummarySensor(_BaseSensor):
    _attr_icon = "mdi:calendar-week"
    _attr_name = "7 Day Mowing Summary"
    _attr_native_unit_of_measurement = "m²"

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_weekly_mowing_summary"

    @property
    def native_value(self):
        summary = _weekly_mowing_summary(self.coordinator)
        return summary.get("total_area")

    @property
    def extra_state_attributes(self):
        summary = _weekly_mowing_summary(self.coordinator)
        return summary or None


class MovaLidaxCleaningHistorySensor(_BaseSensor):
    _attr_icon = "mdi:clipboard-text-history-outline"
    _attr_name = "Mowing History"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        return f"{self.device.mac}_cleaning_history"

    @property
    def native_value(self):
        history = _mowing_history(self.coordinator) or self.device.status.cleaning_history
        return len(history) if history else 0

    @property
    def extra_state_attributes(self):
        history = _mowing_history(self.coordinator) or self.device.status.cleaning_history
        return {"history": history} if history else None


def _latest_cleaning_entry(device):
    history = device.status.cleaning_history
    if not history:
        return None
    return history[0]


def _mowing_history(coordinator):
    history = coordinator.extra_attributes.get("mowing_history")
    return history if isinstance(history, list) else []


def _latest_mowing_entry(coordinator):
    history = _mowing_history(coordinator)
    return history[0] if history else None


def _weekly_mowing_summary(coordinator, days: int = 7):
    history = _mowing_history(coordinator)
    today = dt_util.now().date()
    start_date = today - timedelta(days=days - 1)
    grouped = {
        (start_date + timedelta(days=offset)).isoformat(): {
            "date": (start_date + timedelta(days=offset)).isoformat(),
            "area": 0.0,
            "duration": 0,
            "runs": 0,
            "maps": {},
        }
        for offset in range(days)
    }

    for entry in history:
        if not isinstance(entry, dict):
            continue
        timestamp = entry.get("start_time") or entry.get("created_at")
        entry_date = _date_from_iso(timestamp)
        if entry_date is None or entry_date < start_date or entry_date > today:
            continue
        key = entry_date.isoformat()
        day = grouped[key]
        map_name = entry.get("map_name") or "Unknown"
        area = _coerce_number(entry.get("mowed_area")) or 0.0
        duration = int(_coerce_number(entry.get("duration")) or 0)

        day["area"] = round(day["area"] + area, 2)
        day["duration"] += duration
        day["runs"] += 1
        map_data = day["maps"].setdefault(map_name, {"area": 0.0, "duration": 0, "runs": 0})
        map_data["area"] = round(map_data["area"] + area, 2)
        map_data["duration"] += duration
        map_data["runs"] += 1

    day_rows = []
    by_map: dict[str, dict[str, float | int]] = {}
    for day in sorted(grouped.values(), key=lambda item: item["date"], reverse=True):
        maps = []
        for map_name, map_data in sorted(day["maps"].items()):
            maps.append(
                {
                    "name": map_name,
                    "area": round(map_data["area"], 2),
                    "duration": map_data["duration"],
                    "duration_text": _format_duration(map_data["duration"]),
                    "runs": map_data["runs"],
                }
            )
            total = by_map.setdefault(map_name, {"area": 0.0, "duration": 0, "runs": 0})
            total["area"] = round(float(total["area"]) + float(map_data["area"]), 2)
            total["duration"] = int(total["duration"]) + int(map_data["duration"])
            total["runs"] = int(total["runs"]) + int(map_data["runs"])

        day_rows.append(
            {
                "date": day["date"],
                "area": round(day["area"], 2),
                "duration": day["duration"],
                "duration_text": _format_duration(day["duration"]),
                "runs": day["runs"],
                "maps": maps,
                "maps_summary": "; ".join(
                    f"{item['name']}: {item['area']} m² / {item['duration_text']}" for item in maps
                )
                or "N/A",
            }
        )

    total_area = round(sum(item["area"] for item in day_rows), 2)
    total_duration = sum(item["duration"] for item in day_rows)
    return {
        "days": day_rows,
        "total_area": total_area,
        "total_duration": total_duration,
        "total_duration_text": _format_duration(total_duration),
        "runs": sum(item["runs"] for item in day_rows),
        "by_map": by_map,
    }


def _date_from_iso(value):
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _format_duration(minutes):
    if not isinstance(minutes, int):
        minutes = int(minutes or 0)
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours}h {mins}m"
    if hours:
        return f"{hours}h"
    return f"{mins}m"


def _lidax_runtime_packet(device):
    runtime = getattr(device, "_lidax_live_position", None)
    return runtime if isinstance(runtime, dict) else {}


def _coerce_number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _is_dnd_active(dnd_settings):
    if not isinstance(dnd_settings, dict) or not dnd_settings.get("enabled"):
        return False
    start = dnd_settings.get("start_minutes")
    end = dnd_settings.get("end_minutes")
    if not isinstance(start, int) or not isinstance(end, int):
        return False
    now = dt_util.now()
    current = now.hour * 60 + now.minute
    if start == end:
        return True
    if start < end:
        return start <= current < end
    return current >= start or current < end


def _current_map_total_area(coordinator, device):
    maps = coordinator.extra_attributes.get("maps") or []
    selected_map = device.status.selected_map
    if not selected_map:
        return None
    for item in maps:
        if not isinstance(item, dict):
            continue
        if (
            item.get("map_id") == selected_map.map_id
            or item.get("map_index") == selected_map.map_index
            or item.get("name") == selected_map.map_name
        ):
            return _coerce_number(item.get("total_area"))
    return None


def _resolve_global_runtime_positions(coordinator, device) -> dict:
    maps = coordinator.extra_attributes.get("maps") or []
    selected_map = device.status.selected_map
    current_map = None
    if selected_map:
        for item in maps:
            if item.get("map_id") == selected_map.map_id or item.get("map_index") == selected_map.map_index:
                current_map = item
                break
    if current_map is None and maps:
        current_map = maps[0]
    if current_map is None:
        return {
            "current_position": None,
            "charger_position": None,
            "position_source": None,
            "raw_packet": None,
            "candidates": None,
            "diagnostic_positions": None,
        }
    return _resolve_runtime_positions(coordinator, device, current_map, maps)


def _build_map_svg(map_data: dict, runtime_positions: dict | None = None, all_maps: list[dict] | None = None) -> str | None:
    boundary = map_data.get("boundary") or {}
    x1 = boundary.get("x1")
    y1 = boundary.get("y1")
    x2 = boundary.get("x2")
    y2 = boundary.get("y2")
    if not all(isinstance(v, (int, float)) for v in (x1, y1, x2, y2)):
        return None

    runtime_positions = runtime_positions or {}
    all_maps = [item for item in (all_maps or []) if isinstance(item, dict)]

    map_boundaries = []
    for item in all_maps or [map_data]:
        item_boundary = item.get("boundary") or {}
        bx1 = item_boundary.get("x1")
        by1 = item_boundary.get("y1")
        bx2 = item_boundary.get("x2")
        by2 = item_boundary.get("y2")
        if all(isinstance(v, (int, float)) for v in (bx1, by1, bx2, by2)):
            map_boundaries.append((float(bx1), float(by1), float(bx2), float(by2)))

    if map_boundaries:
        x1 = min(boundary_item[0] for boundary_item in map_boundaries)
        y1 = min(boundary_item[1] for boundary_item in map_boundaries)
        x2 = max(boundary_item[2] for boundary_item in map_boundaries)
        y2 = max(boundary_item[3] for boundary_item in map_boundaries)

    runtime_points = [
        point
        for point in (
            runtime_positions.get("current_position"),
            runtime_positions.get("charger_position"),
        )
        if isinstance(point, dict)
        and isinstance(point.get("x"), (int, float))
        and isinstance(point.get("y"), (int, float))
    ]
    diagnostic_points = [
        point
        for point in (runtime_positions.get("diagnostic_positions") or [])
        if isinstance(point, dict)
        and isinstance(point.get("x"), (int, float))
        and isinstance(point.get("y"), (int, float))
    ]
    stream_points = [
        point
        for point in (runtime_positions.get("m_path_stream_positions") or [])
        if isinstance(point, dict)
        and isinstance(point.get("x"), (int, float))
        and isinstance(point.get("y"), (int, float))
    ]
    mirrored_stream_points = [
        point
        for point in (runtime_positions.get("m_path_stream_positions_mirrored") or [])
        if isinstance(point, dict)
        and isinstance(point.get("x"), (int, float))
        and isinstance(point.get("y"), (int, float))
    ]
    runtime_points.extend(diagnostic_points)
    runtime_points.extend(stream_points)
    runtime_points.extend(mirrored_stream_points)

    if runtime_points:
        runtime_margin = 1200
        x1 = min(float(x1), *(float(point["x"]) - runtime_margin for point in runtime_points))
        y1 = min(float(y1), *(float(point["y"]) - runtime_margin for point in runtime_points))
        x2 = max(float(x2), *(float(point["x"]) + runtime_margin for point in runtime_points))
        y2 = max(float(y2), *(float(point["y"]) + runtime_margin for point in runtime_points))

    width = max(float(x2) - float(x1), 1.0)
    height = max(float(y2) - float(y1), 1.0)
    view_w = 1200
    view_h = max(int(view_w * (height / width)), 420)
    padding = 24
    sx = (view_w - padding * 2) / width
    sy = (view_h - padding * 2) / height

    def point_to_svg(point: dict) -> str | None:
        if not isinstance(point, dict):
            return None
        px = point.get("x")
        py = point.get("y")
        if not isinstance(px, (int, float)) or not isinstance(py, (int, float)):
            return None
        nx = padding + (float(x2) - float(px)) * sx
        ny = padding + (float(py) - float(y1)) * sy
        return f"{nx:.1f},{ny:.1f}"

    def polyline(points: list[dict]) -> str | None:
        coords = [coord for point in points if (coord := point_to_svg(point))]
        return " ".join(coords) if len(coords) >= 2 else None

    zone_palette = [
        "#7dd3fc",
        "#86efac",
        "#f9a8d4",
        "#fcd34d",
        "#c4b5fd",
        "#fdba74",
    ]

    zone_shapes: list[str] = []
    zone_labels: list[str] = []
    map_shell_labels: list[str] = []

    current_map_id = map_data.get("map_id")
    render_maps = all_maps or [map_data]
    for map_index, item in enumerate(render_maps):
        is_active = item.get("map_id") == current_map_id
        item_boundary = item.get("boundary") or {}
        bx1 = item_boundary.get("x1")
        by1 = item_boundary.get("y1")
        bx2 = item_boundary.get("x2")
        by2 = item_boundary.get("y2")
        if all(isinstance(v, (int, float)) for v in (bx1, by1, bx2, by2)):
            top_left = point_to_svg({"x": bx1, "y": by2})
            if top_left:
                lx, ly = top_left.split(",", 1)
                map_shell_labels.append(
                    f'<text x="{float(lx) + 16:.1f}" y="{float(ly) + 30 + map_index * 4:.1f}" '
                    f'fill="{("#e2e8f0" if is_active else "#94a3b8")}" font-size="22" font-weight="{("700" if is_active else "600")}">'
                    f'{escape(item.get("name") or "Mapa")}</text>'
                )

        zone_opacity = "22" if is_active else "10"
        zone_stroke = "5" if is_active else "3"
        label_color_fallback = "#cbd5e1" if is_active else "#94a3b8"
        for index, zone in enumerate(item.get("zones") or []):
            path = polyline(zone.get("path") or [])
            if not path:
                continue
            color = zone_palette[index % len(zone_palette)] if is_active else "#64748b"
            zone_shapes.append(
                f'<polygon points="{path}" fill="{color}{zone_opacity}" stroke="{color}" stroke-width="{zone_stroke}" stroke-linejoin="round" />'
            )
            first = next((point_to_svg(point) for point in (zone.get("path") or []) if point_to_svg(point)), None)
            if first:
                lx, ly = first.split(",", 1)
                zone_labels.append(
                    f'<text x="{lx}" y="{ly}" fill="{color if is_active else label_color_fallback}" font-size="{("28" if is_active else "22")}" font-weight="{("700" if is_active else "500")}">'
                    f'{escape(zone.get("name") or str(zone.get("id") or index + 1))}</text>'
                )

    contour_shapes: list[str] = []
    guide_shapes: list[str] = []
    marker_shapes: list[str] = []
    charger_svg = point_to_svg(runtime_positions.get("charger_position")) if isinstance(runtime_positions, dict) else None
    if charger_svg:
        dx, dy = charger_svg.split(",", 1)
        marker_shapes.append(
            f'<circle cx="{dx}" cy="{dy}" r="11" fill="#f97316" stroke="#fff7ed" stroke-width="3" />'
            f'<text x="{float(dx) + 16:.1f}" y="{float(dy) + 6:.1f}" fill="#fdba74" font-size="22" font-weight="700">Dock</text>'
        )

    current_svg = point_to_svg(runtime_positions.get("current_position")) if isinstance(runtime_positions, dict) else None
    if current_svg:
        mx, my = current_svg.split(",", 1)
        marker_shapes.append(
            f'<circle cx="{mx}" cy="{my}" r="13" fill="#22c55e" stroke="#dcfce7" stroke-width="4" />'
            f'<circle cx="{mx}" cy="{my}" r="24" fill="#22c55e22" stroke="#86efac66" stroke-width="3" />'
            f'<text x="{float(mx) + 18:.1f}" y="{float(my) + 7:.1f}" fill="#86efac" font-size="22" font-weight="700">Mower</text>'
        )

    alt_svg = point_to_svg(runtime_positions.get("m_path_alt_position")) if isinstance(runtime_positions, dict) else None
    if alt_svg:
        ax, ay = alt_svg.split(",", 1)
        marker_shapes.append(
            f'<circle cx="{ax}" cy="{ay}" r="10" fill="#f59e0b" stroke="#fffbeb" stroke-width="3" />'
            f'<circle cx="{ax}" cy="{ay}" r="18" fill="#f59e0b22" stroke="#fbbf2466" stroke-width="2" />'
            f'<text x="{float(ax) + 16:.1f}" y="{float(ay) + 6:.1f}" fill="#fbbf24" font-size="20" font-weight="700">Alt</text>'
        )

    diagnostic_positions = runtime_positions.get("diagnostic_positions") if isinstance(runtime_positions, dict) else None
    diagnostic_palette = [
        "#f472b6",
        "#facc15",
        "#a78bfa",
        "#fb7185",
        "#22d3ee",
        "#f59e0b",
    ]
    if isinstance(diagnostic_positions, list):
        for index, candidate in enumerate(diagnostic_positions[:6]):
            candidate_svg = point_to_svg(candidate)
            if not candidate_svg:
                continue
            cx, cy = candidate_svg.split(",", 1)
            base_x = float(cx)
            base_y = float(cy)
            offset_x = 18 + (index % 3) * 16
            offset_y = -18 - (index // 3) * 18
            display_x = base_x + offset_x
            display_y = base_y + offset_y
            color = diagnostic_palette[index % len(diagnostic_palette)]
            label = escape(candidate.get("label") or f"C{index + 1}")
            marker_shapes.append(
                f'<line x1="{base_x:.1f}" y1="{base_y:.1f}" x2="{display_x:.1f}" y2="{display_y:.1f}" '
                f'stroke="{color}" stroke-width="2.5" stroke-dasharray="5 4" opacity="0.95" />'
                f'<circle cx="{base_x:.1f}" cy="{base_y:.1f}" r="5" fill="{color}" opacity="0.9" />'
                f'<circle cx="{display_x:.1f}" cy="{display_y:.1f}" r="11" fill="{color}" stroke="#0f172a" stroke-width="3" />'
                f'<text x="{display_x + 14:.1f}" y="{display_y + 6:.1f}" fill="{color}" font-size="18" font-weight="700">{label}</text>'
            )

    mirrored_stream_positions = (
        runtime_positions.get("m_path_stream_positions_mirrored") if isinstance(runtime_positions, dict) else None
    )
    stream_palette = ["#60a5fa", "#f59e0b", "#f43f5e", "#a78bfa", "#14b8a6", "#eab308"]
    if isinstance(mirrored_stream_positions, list):
        for index, point in enumerate(mirrored_stream_positions[:6]):
            point_svg = point_to_svg(point)
            if not point_svg:
                continue
            sxp, syp = point_svg.split(",", 1)
            base_x = float(sxp)
            base_y = float(syp)
            offset_x = -26 - (index % 3) * 18
            offset_y = 20 + (index // 3) * 18
            display_x = base_x + offset_x
            display_y = base_y + offset_y
            color = stream_palette[index % len(stream_palette)]
            label = escape(point.get("label") or f"S{index + 1}")
            marker_shapes.append(
                f'<line x1="{base_x:.1f}" y1="{base_y:.1f}" x2="{display_x:.1f}" y2="{display_y:.1f}" '
                f'stroke="{color}" stroke-width="2.5" stroke-dasharray="3 4" opacity="0.95" />'
                f'<circle cx="{base_x:.1f}" cy="{base_y:.1f}" r="4.5" fill="{color}" opacity="0.95" />'
                f'<circle cx="{display_x:.1f}" cy="{display_y:.1f}" r="10" fill="{color}" stroke="#0f172a" stroke-width="3" />'
                f'<text x="{display_x + 13:.1f}" y="{display_y + 6:.1f}" fill="{color}" font-size="17" font-weight="700">m{label}</text>'
            )

    map_name = escape(map_data.get("name") or "Mapa")
    total_area = escape(str(map_data.get("total_area") or "N/A"))
    return (
        f'<svg viewBox="0 0 {view_w} {view_h}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;height:auto;display:block;border-radius:18px;background:linear-gradient(180deg,#102235 0%,#0b1724 100%);">'
        f'<rect x="6" y="6" width="{view_w-12}" height="{view_h-12}" rx="22" ry="22" fill="none" stroke="#27455f" stroke-width="3" />'
        f'{"".join(contour_shapes)}'
        f'{"".join(zone_shapes)}'
        f'{"".join(guide_shapes)}'
        f'{"".join(marker_shapes)}'
        f'{"".join(map_shell_labels)}'
        f'{"".join(zone_labels)}'
        f'<text x="34" y="50" fill="#e2e8f0" font-size="30" font-weight="700">{map_name}</text>'
        f'<text x="34" y="84" fill="#94a3b8" font-size="22">plocha {total_area} m²</text>'
        f"</svg>"
    )


def _point_to_dict(point) -> dict | None:
    if point is None:
        return None
    x = getattr(point, "x", None)
    y = getattr(point, "y", None)
    a = getattr(point, "a", None)
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return None
    result = {"x": x, "y": y}
    if isinstance(a, (int, float)):
        result["a"] = a
    return result


def _scale_m_path_point(point: dict | None, factor: float = 10.0) -> dict | None:
    if not isinstance(point, dict):
        return None
    x = point.get("x")
    y = point.get("y")
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return None
    result = {"x": float(x) * factor, "y": float(y) * factor}
    a = point.get("a")
    if isinstance(a, (int, float)):
        result["a"] = a
    return result


def _map_bounds(maps: list[dict]) -> dict[str, float] | None:
    xs: list[float] = []
    ys: list[float] = []
    for item in maps:
        for point in item.get("boundary") or []:
            if isinstance(point, dict) and isinstance(point.get("x"), (int, float)) and isinstance(point.get("y"), (int, float)):
                xs.append(float(point["x"]))
                ys.append(float(point["y"]))
        for zone in item.get("zones") or []:
            for point in zone.get("path") or []:
                if isinstance(point, dict) and isinstance(point.get("x"), (int, float)) and isinstance(point.get("y"), (int, float)):
                    xs.append(float(point["x"]))
                    ys.append(float(point["y"]))
    if not xs or not ys:
        return None
    return {
        "min_x": min(xs),
        "max_x": max(xs),
        "min_y": min(ys),
        "max_y": max(ys),
    }


def _mirror_point(point: dict | None, bounds: dict[str, float] | None) -> dict | None:
    if not isinstance(point, dict) or not isinstance(bounds, dict):
        return None
    x = point.get("x")
    y = point.get("y")
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return None
    return {
        "x": float(bounds["min_x"] + bounds["max_x"] - float(x)),
        "y": float(bounds["min_y"] + bounds["max_y"] - float(y)),
    }


def _candidate_label(candidate: dict) -> str:
    return f'{candidate.get("byte_order", "le")}/{candidate.get("kind", "i16")}@{candidate.get("index")}'


def _candidate_key(candidate: dict) -> tuple[int, str, str] | None:
    index = candidate.get("index")
    byte_order = candidate.get("byte_order")
    kind = candidate.get("kind", "i16")
    if not isinstance(index, int) or not isinstance(byte_order, str) or not isinstance(kind, str):
        return None
    return (index, byte_order, kind)


def _resolve_runtime_positions(coordinator, device, current_map: dict, all_maps: list[dict] | None = None) -> dict:
    runtime_map = getattr(device.status, "current_map", None)
    charger_position = None
    current_position = None
    position_source = None
    mqtt_position = getattr(device, "_lidax_live_position", None)
    raw_packet = mqtt_position.get("raw_packet") if isinstance(mqtt_position, dict) else None
    candidates = mqtt_position.get("candidates") if isinstance(mqtt_position, dict) else None
    dock_candidates = getattr(device, "_lidax_dock_candidates", None)
    m_path_stream_positions = None
    m_path_alt_position = None
    bounds = _map_bounds(all_maps or [current_map]) or _map_bounds([current_map])

    if runtime_map is not None:
        charger_position = _point_to_dict(
            getattr(runtime_map, "optimized_charger_position", None) or getattr(runtime_map, "charger_position", None)
        )
        current_position = _point_to_dict(getattr(runtime_map, "robot_position", None))
        if charger_position or current_position:
            position_source = "runtime_map"

    if current_position is None:
        raw_position = coordinator.extra_attributes.get("raw_position")
        if isinstance(raw_position, dict):
            current_position = _scale_m_path_point(raw_position)
            position_source = position_source or "m_path_raw_x10"

    if current_position is None:
        if isinstance(current_map.get("moving_position"), dict):
            current_position = _scale_m_path_point(current_map["moving_position"])
            position_source = position_source or "m_path_x10"

    if current_position is None:
        if isinstance(mqtt_position, dict):
            current_position = {k: v for k, v in mqtt_position.items() if k in {"x", "y", "a"} and isinstance(v, (int, float))}
            position_source = position_source or "mqtt_1_4"

    if charger_position is None:
        for path_item in current_map.get("paths") or []:
            path = path_item.get("path") or []
            if path:
                candidate = path[-1]
                if isinstance(candidate, dict) and isinstance(candidate.get("x"), (int, float)) and isinstance(
                    candidate.get("y"), (int, float)
                ):
                    charger_position = {"x": candidate["x"], "y": candidate["y"]}
                    position_source = position_source or "path_heuristic"
                    break

    if (
        isinstance(current_position, dict)
        and isinstance(charger_position, dict)
        and position_source in {"mqtt_1_4", "mqtt_1_4_calibrated"}
    ):
        offset = getattr(device, "_lidax_position_offset", None)
        if getattr(device.status, "docked", False):
            device._lidax_recently_docked_at = datetime.now().timestamp()
            offset = {
                "x": float(charger_position["x"]) - float(current_position["x"]),
                "y": float(charger_position["y"]) - float(current_position["y"]),
            }
            device._lidax_position_offset = offset

        if isinstance(offset, dict):
            current_position = {
                **current_position,
                "x": float(current_position["x"]) + float(offset.get("x", 0)),
                "y": float(current_position["y"]) + float(offset.get("y", 0)),
            }
            if position_source == "mqtt_1_4":
                position_source = "mqtt_1_4_calibrated"

    if current_position is None and getattr(device.status, "docked", False) and charger_position is not None:
        current_position = dict(charger_position)
        position_source = position_source or "docked_fallback"

    diagnostic_positions = None
    if isinstance(candidates, list):
        bounds = _map_bounds(all_maps or [current_map]) or _map_bounds([current_map])
        if bounds:
            width = bounds["max_x"] - bounds["min_x"]
            height = bounds["max_y"] - bounds["min_y"]
            x_margin = max(width * 0.35, 60)
            y_margin = max(height * 0.35, 60)
            x_candidates: list[dict] = []
            y_candidates: list[dict] = []
            for item in candidates:
                if not isinstance(item, dict):
                    continue
                value = item.get("value")
                if not isinstance(value, (int, float)):
                    continue
                if item.get("kind") == "f32":
                    continue
                if abs(value) > 100000:
                    continue
                enriched = {
                    **item,
                    "label": _candidate_label(item),
                    "score": abs(float(item.get("delta", 0))),
                }
                if bounds["min_x"] - x_margin <= float(value) <= bounds["max_x"] + x_margin:
                    x_candidates.append(enriched)
                if bounds["min_y"] - y_margin <= float(value) <= bounds["max_y"] + y_margin:
                    y_candidates.append(enriched)

            x_candidates.sort(key=lambda item: (item["score"], 1 if item.get("kind") == "i32" else 0), reverse=True)
            y_candidates.sort(key=lambda item: (item["score"], 1 if item.get("kind") == "i32" else 0), reverse=True)

            diagnostic_positions = []
            if isinstance(charger_position, dict) and isinstance(dock_candidates, dict):
                baseline_map = {
                    key: value
                    for key, value in dock_candidates.items()
                    if isinstance(key, tuple) and isinstance(value, (int, float))
                }
                for x_candidate in x_candidates[:4]:
                    x_key = _candidate_key(x_candidate)
                    x_baseline = baseline_map.get(x_key) if x_key is not None else None
                    if not isinstance(x_baseline, (int, float)):
                        continue
                    dx = float(x_candidate["value"]) - float(x_baseline)
                    for y_candidate in y_candidates[:6]:
                        if (
                            x_candidate.get("index") == y_candidate.get("index")
                            and x_candidate.get("byte_order") == y_candidate.get("byte_order")
                            and x_candidate.get("kind") == y_candidate.get("kind")
                        ):
                            continue
                        y_key = _candidate_key(y_candidate)
                        y_baseline = baseline_map.get(y_key) if y_key is not None else None
                        if not isinstance(y_baseline, (int, float)):
                            continue
                        dy = float(y_candidate["value"]) - float(y_baseline)
                        for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                            sx_label = "+" if sx > 0 else "-"
                            sy_label = "+" if sy > 0 else "-"
                            point = {
                                "x": float(charger_position["x"]) + (dx * sx),
                                "y": float(charger_position["y"]) + (dy * sy),
                                "label": f'rel {x_candidate["label"]}+{y_candidate["label"]} {sx_label}/{sy_label}',
                                "x_label": x_candidate["label"],
                                "y_label": y_candidate["label"],
                                "mode": "relative_to_dock",
                            }
                            if (
                                bounds["min_x"] - x_margin <= point["x"] <= bounds["max_x"] + x_margin
                                and bounds["min_y"] - y_margin <= point["y"] <= bounds["max_y"] + y_margin
                            ):
                                diagnostic_positions.append(point)
                        if len(diagnostic_positions) >= 12:
                            break
                    if len(diagnostic_positions) >= 12:
                        break

            if not diagnostic_positions:
                for x_candidate in x_candidates[:6]:
                    for y_candidate in y_candidates[:8]:
                        if (
                            x_candidate.get("index") == y_candidate.get("index")
                            and x_candidate.get("byte_order") == y_candidate.get("byte_order")
                            and x_candidate.get("kind") == y_candidate.get("kind")
                        ):
                            continue
                        diagnostic_positions.append(
                            {
                                "x": float(x_candidate["value"]),
                                "y": float(y_candidate["value"]),
                                "label": f'{x_candidate["label"]}+{y_candidate["label"]}',
                                "x_label": x_candidate["label"],
                                "y_label": y_candidate["label"],
                                "mode": "absolute",
                            }
                        )
                        if len(diagnostic_positions) >= 16:
                            break
                    if len(diagnostic_positions) >= 16:
                        break

    moving_streams = coordinator.extra_attributes.get("moving_streams")
    m_path_stream_positions_mirrored = None
    if isinstance(moving_streams, list):
        recent = []
        for stream in moving_streams[-8:]:
            if not isinstance(stream, dict):
                continue
            point = _scale_m_path_point(stream.get("current_position"))
            if not isinstance(point, dict):
                continue
            label = f's{stream.get("map_index")}'
            recent.append({**point, "label": label})
        if recent:
            m_path_stream_positions = recent
            if bounds:
                mirrored = []
                for point in recent:
                    mirrored_point = _mirror_point(point, bounds)
                    if isinstance(mirrored_point, dict):
                        mirrored.append({**mirrored_point, "label": point.get("label")})
                if mirrored:
                    m_path_stream_positions_mirrored = mirrored

    if position_source in {"m_path_raw_x10", "m_path_x10"} and isinstance(current_position, dict):
        m_path_alt_position = _mirror_point(current_position, bounds)

    return {
        "current_position": current_position,
        "charger_position": charger_position,
        "position_source": position_source,
        "raw_packet": raw_packet,
        "candidates": candidates,
        "diagnostic_positions": diagnostic_positions,
        "m_path_stream_positions": m_path_stream_positions,
        "m_path_stream_positions_mirrored": m_path_stream_positions_mirrored,
        "m_path_alt_position": m_path_alt_position,
    }


def _parse_prefixed_number(value):
    if not isinstance(value, str):
        return None
    token = value.split(" ", 1)[0]
    try:
        return float(token) if "." in token else int(token)
    except ValueError:
        return None


def _packet_to_hex(packet) -> str | None:
    if not isinstance(packet, list) or not packet:
        return None
    values = [value for value in packet if isinstance(value, int)]
    if not values:
        return None
    return " ".join(f"{value:02X}" for value in values)


def _packet_to_indexed_bytes(packet) -> list[str] | None:
    if not isinstance(packet, list) or not packet:
        return None
    indexed = []
    for index, value in enumerate(packet):
        if not isinstance(value, int):
            continue
        indexed.append(f"b{index}={value} (0x{value:02X})")
    return indexed or None
