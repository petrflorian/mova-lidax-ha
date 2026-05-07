"""Coordinator for MOVA LiDAX."""

from __future__ import annotations

import json
import re
import time
import traceback
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .dreame import DreameMowerDevice

from .const import (
    CONF_ACCOUNT_TYPE,
    CONF_COUNTRY,
    CONF_DID,
    CONF_MAC,
    DOMAIN,
    ENABLE_DEBUG_SNAPSHOT,
    EXTRA_BATCH_KEYS,
    LOGGER,
)


class MovaLidaxCoordinator(DataUpdateCoordinator[DreameMowerDevice]):
    """Bridge the LiDAX device into Home Assistant."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.extra_batch_data: dict[str, Any] = {}
        self.extra_attributes: dict[str, Any] = {}
        self._last_extra_refresh: float = 0.0
        self._last_cloud_summary_refresh: float = 0.0
        self._last_dnd_refresh: float = 0.0
        self._last_mowing_history_refresh: float = 0.0
        self._device = DreameMowerDevice(
            entry.data[CONF_NAME],
            "",
            "",
            entry.data.get(CONF_MAC),
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            entry.data[CONF_COUNTRY],
            True,
            entry.data.get(CONF_ACCOUNT_TYPE, "mova"),
            entry.data[CONF_DID],
        )
        self._device.listen(self.set_updated_data)
        self._device.listen_error(self.set_update_error)
        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=timedelta(seconds=5))

    @property
    def device(self) -> DreameMowerDevice:
        return self._device

    async def _async_update_data(self) -> DreameMowerDevice:
        """Initial refresh."""
        try:
            await self.hass.async_add_executor_job(self._device.update)
            await self.hass.async_add_executor_job(self._refresh_extra_data)
            self._device.schedule_update()
            self.async_set_updated_data()
            return self._device
        except Exception as ex:
            LOGGER.warning("LiDAX start failed: %s", traceback.format_exc())
            raise UpdateFailed(ex) from ex

    def set_update_error(self, ex=None) -> None:
        self.hass.loop.call_soon_threadsafe(self.async_set_update_error, ex)

    def set_updated_data(self, device=None) -> None:
        self.hass.loop.call_soon_threadsafe(self._handle_device_update, device)

    @callback
    def async_set_updated_data(self, device=None) -> None:
        super().async_set_updated_data(self._device)

    @callback
    def _handle_device_update(self, device=None) -> None:
        if time.monotonic() - self._last_extra_refresh >= 2:
            self.hass.async_create_task(self._async_refresh_extra_data())
        else:
            self.async_set_updated_data(device)

    async def _async_refresh_extra_data(self) -> None:
        await self.hass.async_add_executor_job(self._refresh_extra_data)
        self.async_set_updated_data(self._device)

    def _refresh_extra_data(self) -> None:
        self._last_extra_refresh = time.monotonic()
        cloud_summary: dict[str, Any] | None = None
        dnd_settings: dict[str, Any] | None = None
        mowing_history: list[dict[str, Any]] | None = None
        if time.monotonic() - self._last_cloud_summary_refresh >= 60:
            cloud_summary = self._refresh_cloud_summary()
        if time.monotonic() - self._last_dnd_refresh >= 60:
            dnd_settings = self._refresh_dnd_settings()
        if time.monotonic() - self._last_mowing_history_refresh >= 120:
            mowing_history = self._refresh_mowing_history()
        try:
            response = self._device._protocol.cloud.get_batch_device_datas(list(EXTRA_BATCH_KEYS))
        except Exception:
            LOGGER.debug("Unable to refresh LiDAX extra batch data", exc_info=True)
            extra_attributes = dict(self.extra_attributes)
            if cloud_summary is not None:
                extra_attributes["cloud_summary"] = cloud_summary
            if dnd_settings is not None:
                extra_attributes["dnd_settings"] = dnd_settings
            if mowing_history is not None:
                extra_attributes["mowing_history"] = mowing_history
            self.extra_attributes = extra_attributes
            return

        if not isinstance(response, Mapping):
            extra_attributes = dict(self.extra_attributes)
            if cloud_summary is not None:
                extra_attributes["cloud_summary"] = cloud_summary
            if dnd_settings is not None:
                extra_attributes["dnd_settings"] = dnd_settings
            if mowing_history is not None:
                extra_attributes["mowing_history"] = mowing_history
            self.extra_attributes = extra_attributes
            return

        previous_attributes = dict(self.extra_attributes)
        extra_attributes = self._decode_extra_batch_data(response)
        self.extra_batch_data = dict(response)

        # Fast batch refreshes run every few seconds, while cloud summary and
        # mowing history are intentionally throttled. Preserve the last known
        # slow-refresh payloads so their sensors do not flicker to unknown.
        extra_attributes["cloud_summary"] = (
            cloud_summary if cloud_summary is not None else previous_attributes.get("cloud_summary")
        )
        extra_attributes["dnd_settings"] = (
            dnd_settings
            if dnd_settings is not None
            else extra_attributes.get("dnd_settings") or previous_attributes.get("dnd_settings")
        )
        extra_attributes["mowing_history"] = (
            mowing_history if mowing_history is not None else previous_attributes.get("mowing_history")
        )
        self.extra_attributes = extra_attributes
        self._write_debug_snapshot(response, extra_attributes)

    def _refresh_cloud_summary(self) -> dict[str, Any] | None:
        self._last_cloud_summary_refresh = time.monotonic()
        try:
            response = self._device._protocol.cloud.get_device_info()
        except Exception:
            LOGGER.debug("Unable to refresh LiDAX cloud summary", exc_info=True)
            return self.extra_attributes.get("cloud_summary")

        if not isinstance(response, Mapping):
            return self.extra_attributes.get("cloud_summary")

        summary = {
            "did": response.get("did"),
            "model": response.get("model"),
            "online": response.get("online"),
            "latest_status": response.get("latestStatus"),
            "battery": response.get("battery"),
            "video_status": response.get("videoStatus"),
            "monitor_status": response.get("monitorStatus"),
            "update_time": response.get("updateTime"),
            "version": response.get("ver"),
            "bind_domain": response.get("bindDomain"),
        }
        device_info = response.get("deviceInfo")
        if isinstance(device_info, Mapping):
            summary["display_name"] = device_info.get("displayName")
            summary["feature"] = device_info.get("feature")
            summary["sc_type"] = device_info.get("scType")
            summary["permit"] = device_info.get("permit")
            summary["device_status"] = device_info.get("status")
        LOGGER.debug("LiDAX cloud summary refreshed: %s", summary)
        return summary

    def _refresh_dnd_settings(self) -> dict[str, Any] | None:
        self._last_dnd_refresh = time.monotonic()
        try:
            response = self._device._protocol.action(2, 50, [{"t": "DND", "m": "g"}])
        except Exception:
            LOGGER.debug("Unable to refresh LiDAX DND settings", exc_info=True)
            return self.extra_attributes.get("dnd_settings")

        dnd = self._parse_dnd_action_response(response)
        if dnd is None:
            return self.extra_attributes.get("dnd_settings")
        dnd["raw_action"] = response
        LOGGER.debug("LiDAX DND settings refreshed: %s", dnd)
        return dnd

    def _refresh_mowing_history(self) -> list[dict[str, Any]] | None:
        self._last_mowing_history_refresh = time.monotonic()
        try:
            response = self._device._protocol.cloud.get_device_event("4.1", limit=20)
        except Exception:
            LOGGER.debug("Unable to refresh LiDAX mowing history", exc_info=True)
            return self.extra_attributes.get("mowing_history")

        if not isinstance(response, list):
            return self.extra_attributes.get("mowing_history")

        history: list[dict[str, Any]] = []
        for event in response:
            if not isinstance(event, Mapping):
                continue
            raw_history = event.get("history")
            try:
                values = json.loads(raw_history) if isinstance(raw_history, str) else raw_history
            except Exception:
                LOGGER.debug("Unable to decode LiDAX mowing history event: %s", event, exc_info=True)
                continue
            if not isinstance(values, list):
                continue
            by_piid = {
                item.get("piid"): item.get("value")
                for item in values
                if isinstance(item, Mapping) and "piid" in item
            }
            created_ms = event.get("createTime")
            started_ts = by_piid.get(8)
            area_raw = by_piid.get(3)
            duration_raw = by_piid.get(2)
            history.append(
                {
                    "event_id": event.get("id"),
                    "created_at": self._format_epoch_ms(created_ms),
                    "start_time": self._format_epoch_seconds(started_ts),
                    "completion_percent": by_piid.get(1),
                    # LiDAX event 4.1 reports area as centi-square-meters in observed app data.
                    "mowed_area": round(area_raw / 100, 2) if isinstance(area_raw, (int, float)) else None,
                    "duration": duration_raw if isinstance(duration_raw, (int, float)) else None,
                    "status_code": by_piid.get(7),
                    "map_file": by_piid.get(9),
                    "interruptions": by_piid.get(13),
                    "map_area": by_piid.get(14),
                    "map_name": by_piid.get(16),
                    "raw_piids": by_piid,
                }
            )
        if history:
            LOGGER.debug("LiDAX mowing history refreshed: %s", history[:3])
            return history
        return self.extra_attributes.get("mowing_history")

    @staticmethod
    def _format_epoch_ms(value: Any) -> str | None:
        if not isinstance(value, (int, float)):
            return None
        try:
            return datetime.fromtimestamp(value / 1000).isoformat()
        except Exception:
            return None

    @staticmethod
    def _format_epoch_seconds(value: Any) -> str | None:
        if not isinstance(value, (int, float)):
            return None
        try:
            return datetime.fromtimestamp(value).isoformat()
        except Exception:
            return None

    def get_schedule_entry(self, map_id: int, schedule_id: int) -> dict[str, Any] | None:
        schedules = self.extra_attributes.get("schedules") or []
        for schedule in schedules:
            if schedule.get("map_id") != map_id:
                continue
            for entry in schedule.get("entries", []):
                if entry.get("schedule_id") == schedule_id:
                    return entry
        return None

    def update_schedule_entry(
        self,
        map_id: int,
        schedule_id: int,
        *,
        enabled: bool | None = None,
        mode: int | None = None,
        time_minutes: int | None = None,
        weekdays: list[int] | None = None,
        zones: list[int] | None = None,
    ) -> Any:
        entry = self.get_schedule_entry(map_id, schedule_id)
        if entry is None:
            raise ValueError(f"Schedule {schedule_id} for map {map_id} was not found")

        payload = [
            schedule_id,
            map_id,
            entry.get("enabled") if enabled is None else enabled,
            entry.get("mode") if mode is None else mode,
            entry.get("time_minutes") if time_minutes is None else time_minutes,
            entry.get("weekdays") if weekdays is None else weekdays,
            entry.get("zones") if zones is None else zones,
        ]
        result = self._device._protocol.action(2, 50, [{"t": "SCHDC", "d": payload, "m": "s"}])
        self._refresh_extra_data()
        return result

    def _decode_extra_batch_data(self, response: Mapping[str, Any]) -> dict[str, Any]:
        data: dict[str, Any] = {}
        maps = self._decode_chunked_json_array(response, "MAP")
        moving_paths = self._decode_m_path(response)
        schedules = self._decode_chunked_json_array(response, "SCHEDULE_TASK")
        dnd_task = self._decode_chunked_json_array(response, "DND_TASK")
        dnd = self._decode_chunked_json_array(response, "DND")
        path = self._decode_simple_json(response.get("PATH.0"))
        cruise = self._decode_simple_json(response.get("CRUISE.0"))
        ota = self._decode_simple_json(response.get("OTA_INFO.0"))
        ai_obs = self._decode_simple_json(response.get("AI_OBS.0"))
        fbd_ntype = self._decode_simple_json(response.get("FBD_NTYPE.0"))
        taskid = self._decode_simple_json(response.get("TASKID.0"))

        if isinstance(maps, list):
            parsed_maps: list[dict[str, Any]] = []
            for raw_map in maps:
                if not isinstance(raw_map, str):
                    continue
                parsed_map = self._decode_simple_json(raw_map)
                if isinstance(parsed_map, Mapping):
                    zones = parsed_map.get("mowingAreas", {}).get("value", [])
                    parsed_maps.append(
                        {
                            "map_id": parsed_map.get("mapIndex"),
                            "name": parsed_map.get("name"),
                            "map_index": parsed_map.get("mapIndex"),
                            "total_area": parsed_map.get("totalArea"),
                            "boundary": parsed_map.get("boundary"),
                            "zone_count": len(zones),
                            "zones": [
                                {
                                    "id": zone_id,
                                    "name": zone.get("name"),
                                    "area": zone.get("area"),
                                    "time": zone.get("time"),
                                    "etime": zone.get("etime"),
                                    "path": zone.get("path"),
                                }
                                for zone_id, zone in zones
                                if isinstance(zone, Mapping)
                            ],
                            "paths": [
                                {
                                    "id": path_id,
                                    "type": path.get("type"),
                                    "shape_type": path.get("shapeType"),
                                    "path": path.get("path"),
                                }
                                for path_id, path in parsed_map.get("paths", {}).get("value", [])
                                if isinstance(path, Mapping)
                            ],
                            "contours": [
                                {
                                    "id": contour_id,
                                    "type": contour.get("type"),
                                    "shape_type": contour.get("shapeType"),
                                    "time": contour.get("time"),
                                    "etime": contour.get("etime"),
                                    "path": contour.get("path"),
                                }
                                for contour_id, contour in parsed_map.get("contours", {}).get("value", [])
                                if isinstance(contour, Mapping)
                            ],
                            "moving_path": [],
                            "mowed_segments": [],
                            "moving_position": None,
                        }
                    )
            if parsed_maps:
                self._apply_runtime_map_hint(parsed_maps)
                if isinstance(moving_paths, list):
                    for item in parsed_maps:
                        item["moving_path"] = []
                        item["moving_position"] = None
                    merged_points = [
                        point
                        for stream in moving_paths
                        if isinstance(stream, Mapping)
                        for point in (stream.get("points") or [])
                        if isinstance(point, Mapping)
                    ]
                    current_position = next(
                        (
                            stream.get("current_position")
                            for stream in reversed(moving_paths)
                            if isinstance(stream, Mapping) and isinstance(stream.get("current_position"), Mapping)
                        ),
                        None,
                    )
                    selected_map = self._device.status.selected_map
                    target_map = None
                    if selected_map is not None:
                        for item in parsed_maps:
                            if item.get("map_id") == selected_map.map_id:
                                target_map = item
                                break
                            if item.get("map_index") == selected_map.map_index:
                                target_map = item
                                break
                            if item.get("name") == selected_map.map_name:
                                target_map = item
                                break
                    if target_map is not None:
                        target_map["moving_path"] = merged_points
                        target_map["mowed_segments"] = self._m_path_mowed_segments(moving_paths, target_map)
                        target_map["moving_position"] = dict(current_position) if current_position is not None else None
                data["maps"] = parsed_maps
        if isinstance(moving_paths, list):
            data["moving_streams"] = moving_paths
            raw_position = next(
                (
                    stream.get("current_position")
                    for stream in reversed(moving_paths)
                    if isinstance(stream, Mapping) and isinstance(stream.get("current_position"), Mapping)
                ),
                None,
            )
            if raw_position is not None:
                data["raw_position"] = dict(raw_position)

        data["schedules"] = self._parse_schedules(schedules, data.get("maps", []))
        parsed_dnd = self._parse_dnd_settings(dnd_task, dnd)
        if parsed_dnd is not None:
            data["dnd_settings"] = parsed_dnd

        if path is not None:
            parsed_paths: list[dict[str, Any]] = []
            if isinstance(path, list):
                for map_index, path_item in enumerate(path):
                    settings = path_item.get("settings", {}) if isinstance(path_item, Mapping) else {}
                    parsed_paths.append(
                        {
                            "map_id": map_index,
                            "map_index": map_index,
                            "settings": settings,
                            "avoid_obstacles": next(
                                (
                                    item.get("avoid_obs")
                                    for item in settings.values()
                                    if isinstance(item, Mapping) and "avoid_obs" in item
                                ),
                                None,
                            ),
                        }
                    )
            data["path"] = parsed_paths if parsed_paths else path
        if cruise is not None:
            data["cruise"] = cruise
        if ota is not None:
            data["ota_info"] = ota
        if ai_obs is not None:
            data["ai_obstacle_detection"] = ai_obs
        if fbd_ntype is not None:
            data["fbd_ntype"] = fbd_ntype
        if taskid is not None:
            data["taskid"] = taskid

        return data

    def _write_debug_snapshot(self, response: Mapping[str, Any], extra_attributes: Mapping[str, Any]) -> None:
        """Persist a compact live-data snapshot outside recorder limits."""
        if not ENABLE_DEBUG_SNAPSHOT:
            return
        runtime = getattr(self._device, "_lidax_live_position", None)
        m_path_keys = sorted(
            (key for key in response if isinstance(key, str) and key.startswith("M_PATH.")),
            key=lambda value: (value != "M_PATH.info", value),
        )
        snapshot = {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "selected_map": {
                "id": getattr(self._device.status.selected_map, "map_id", None),
                "index": getattr(self._device.status.selected_map, "map_index", None),
                "name": getattr(self._device.status.selected_map, "map_name", None),
            },
            "runtime": runtime if isinstance(runtime, Mapping) else None,
            "dnd_settings": extra_attributes.get("dnd_settings"),
            "fbd_ntype": extra_attributes.get("fbd_ntype"),
            "taskid": extra_attributes.get("taskid"),
            "raw_position": extra_attributes.get("raw_position"),
            "m_path": {
                "info": response.get("M_PATH.info"),
                "chunk_count": len([key for key in m_path_keys if key != "M_PATH.info"]),
                "keys": m_path_keys[:40],
                "streams": self._summarize_streams(extra_attributes.get("moving_streams")),
                "raw_prefix": self._join_prefix(response, "M_PATH", 1200),
            },
            "map_summaries": [
                {
                    "map_id": item.get("map_id"),
                    "map_index": item.get("map_index"),
                    "name": item.get("name"),
                    "total_area": item.get("total_area"),
                    "zones": item.get("zone_count"),
                    "boundary": item.get("boundary"),
                    "moving_path_points": len(item.get("moving_path") or []),
                    "mowed_segment_count": len(item.get("mowed_segments") or []),
                    "moving_position": item.get("moving_position"),
                }
                for item in (extra_attributes.get("maps") or [])
                if isinstance(item, Mapping)
            ],
            "schedules": extra_attributes.get("schedules"),
            "raw_schedule": {
                "info": response.get("SCHEDULE_TASK.info"),
                "raw_prefix": self._join_prefix(response, "SCHEDULE_TASK", 2000),
            },
            "raw_dnd": {
                "DND_TASK.info": response.get("DND_TASK.info"),
                "DND_TASK.0": response.get("DND_TASK.0"),
                "DND.info": response.get("DND.info"),
                "DND.0": response.get("DND.0"),
            },
        }
        try:
            path = Path(self.hass.config.path("www", "mova-lidax-debug.json"))
            path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            LOGGER.debug("Unable to write LiDAX debug snapshot", exc_info=True)

    @staticmethod
    def _join_prefix(response: Mapping[str, Any], prefix: str, limit: int) -> str | None:
        chunks: list[str] = []
        index = 0
        while True:
            value = response.get(f"{prefix}.{index}")
            if not isinstance(value, str):
                break
            chunks.append(value)
            index += 1
        if not chunks:
            return None
        return "".join(chunks)[:limit]

    @classmethod
    def _summarize_streams(cls, streams: Any) -> list[dict[str, Any]]:
        if not isinstance(streams, list):
            return []
        return [
            {
                "map_id": stream.get("map_id"),
                "map_index": stream.get("map_index"),
                "point_count": len(points),
                "first": points[0] if points else None,
                "last": points[-1] if points else None,
                "bounds": cls._point_bounds(points),
            }
            for stream in streams
            if isinstance(stream, Mapping)
            for points in [stream.get("points") or []]
            if isinstance(points, list)
        ]

    @staticmethod
    def _point_bounds(points: list[Any]) -> dict[str, Any] | None:
        xy = [
            (point.get("x"), point.get("y"))
            for point in points
            if isinstance(point, Mapping)
            and isinstance(point.get("x"), (int, float))
            and isinstance(point.get("y"), (int, float))
        ]
        if not xy:
            return None
        xs = [item[0] for item in xy]
        ys = [item[1] for item in xy]
        return {"x1": min(xs), "y1": min(ys), "x2": max(xs), "y2": max(ys)}

    @staticmethod
    def _m_path_mowed_segments(streams: Any, map_data: Mapping[str, Any]) -> list[dict[str, Any]]:
        boundary = map_data.get("boundary") if isinstance(map_data, Mapping) else None
        if not isinstance(streams, list) or not isinstance(boundary, Mapping):
            return []
        bx1 = boundary.get("x1")
        by1 = boundary.get("y1")
        bx2 = boundary.get("x2")
        by2 = boundary.get("y2")
        if not all(isinstance(value, (int, float)) for value in (bx1, by1, bx2, by2)):
            return []
        left = min(float(bx1), float(bx2))
        right = max(float(bx1), float(bx2))
        bottom = min(float(by1), float(by2))
        top = max(float(by1), float(by2))
        segments: list[dict[str, Any]] = []
        for stream in streams:
            if not isinstance(stream, Mapping):
                continue
            raw_points = stream.get("points") or []
            if not isinstance(raw_points, list) or len(raw_points) < 2:
                continue
            points = []
            for point in raw_points:
                if not isinstance(point, Mapping):
                    continue
                x = point.get("x")
                y = point.get("y")
                if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                    points.append({"x": float(x) * 10.0, "y": float(y) * 10.0})
            for first, second in zip(points, points[1:]):
                y = (first["y"] + second["y"]) / 2.0
                if y < bottom or y > top:
                    continue
                x_start = min(first["x"], second["x"])
                x_end = max(first["x"], second["x"])
                if x_end < left or x_start > right:
                    continue
                segments.append(
                    {
                        "x1": max(x_start, left),
                        "y1": y,
                        "x2": min(x_end, right),
                        "y2": y,
                    }
                )
        return segments[:2500]

    def _apply_runtime_map_hint(self, parsed_maps: list[dict[str, Any]]) -> None:
        """Select the active map when live runtime area uniquely identifies it."""
        if not self._device._map_manager:
            return

        if self._device.status.selected_map is not None:
            return

        runtime = getattr(self._device, "_lidax_live_position", None)
        target_area = runtime.get("mowing_target_area") if isinstance(runtime, Mapping) else None
        if not isinstance(target_area, (int, float)):
            return

        matches = [
            item
            for item in parsed_maps
            if isinstance(item.get("total_area"), (int, float))
            and abs(float(item["total_area"]) - float(target_area)) <= 2
        ]
        if len(matches) != 1:
            return

        map_id = matches[0].get("map_id")
        if not isinstance(map_id, int) or map_id not in self._device.status.map_data_list:
            return

        LOGGER.info(
            "LiDAX runtime target area %.2f m2 matches map %s, selecting it as HA context",
            target_area,
            matches[0].get("name") or map_id,
        )
        self._device._map_manager.editor.set_selected_map(map_id)

    @staticmethod
    def _decode_simple_json(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        try:
            return json.loads(value)
        except Exception:
            return value

    def _parse_schedules(self, schedules: Any, maps: Any) -> list[dict[str, Any]]:
        """Decode LiDAX schedule slots and hide stale/deleted app records."""
        if not isinstance(schedules, list):
            return []

        parsed_schedules: list[dict[str, Any]] = []
        has_deleted_or_stale_entry = False
        map_lookup = {item.get("map_id"): item for item in maps if isinstance(item, Mapping)}
        for map_index, raw_schedule in enumerate(schedules):
            decoded_schedule = self._decode_simple_json(raw_schedule)
            if not isinstance(decoded_schedule, list) or not decoded_schedule:
                continue

            schedule_entries = []
            skipped_entries = []
            primary_entries = decoded_schedule[0].get("value", []) if isinstance(decoded_schedule[0], Mapping) else []
            for raw_item in primary_entries:
                if not isinstance(raw_item, list) or len(raw_item) < 2:
                    continue
                schedule_id, payload = raw_item[0], raw_item[1]
                if not isinstance(payload, list) or len(payload) < 2:
                    continue
                entry = payload[1]
                if not isinstance(entry, list) or len(entry) < 6:
                    continue

                if not self._is_visible_schedule_entry(entry):
                    has_deleted_or_stale_entry = True
                    skipped_entries.append(
                        {
                            "schedule_id": schedule_id,
                            "job_id": payload[0],
                            "raw_entry": entry,
                            "reason": "disabled_or_deleted",
                        }
                    )
                    continue

                minutes = entry[3] if len(entry) > 3 else None
                weekdays = entry[4] if len(entry) > 4 else None
                zones = entry[5] if len(entry) > 5 else None
                zone_lookup = {
                    zone.get("id"): zone.get("name")
                    for zone in map_lookup.get(map_index, {}).get("zones", [])
                    if isinstance(zone, Mapping)
                }
                schedule_entries.append(
                    {
                        "schedule_id": schedule_id,
                        "job_id": payload[0],
                        "map_id": map_index,
                        "map_index": map_index,
                        "enabled": True,
                        "mode": entry[0] if len(entry) > 0 else None,
                        "visibility_flag": entry[1] if len(entry) > 1 else None,
                        "time_minutes": minutes,
                        "time": self._format_minutes(minutes),
                        "weekdays": weekdays,
                        "weekday_names": self._format_weekdays(weekdays),
                        "zones": zones,
                        "zone_names": [zone_lookup.get(zone_id, f"Zone {zone_id}") for zone_id in (zones or [])],
                        # Experimental LiDAX write payload based on observed SCHDC app traffic.
                        "schdc_data": [
                            schedule_id,
                            map_index,
                            True,
                            entry[0] if len(entry) > 0 else None,
                            minutes,
                            weekdays,
                            zones,
                        ],
                        "raw_entry": entry,
                    }
                )

            parsed_schedules.append(
                {
                    "map_id": map_index,
                    "map_index": map_index,
                    "map_name": map_lookup.get(map_index, {}).get("name"),
                    "entries": schedule_entries,
                    "skipped_entries": skipped_entries,
                }
            )

        if has_deleted_or_stale_entry:
            LOGGER.debug(
                "LiDAX SCHEDULE_TASK contains stale/deleted records; suppressing active schedule sensors: %s",
                parsed_schedules,
            )
            return [
                {
                    "map_id": item.get("map_id"),
                    "map_index": item.get("map_index"),
                    "map_name": item.get("map_name"),
                    "entries": [],
                    "skipped_entries": (item.get("skipped_entries") or []) + (item.get("entries") or []),
                }
                for item in parsed_schedules
            ]
        return parsed_schedules

    def _parse_dnd_settings(self, dnd_task: Any, dnd: Any = None) -> dict[str, Any] | None:
        task_value = dnd_task
        if isinstance(dnd_task, list) and len(dnd_task) == 1:
            task_value = dnd_task[0]
        tasks = self._decode_simple_json(task_value)
        if isinstance(tasks, str):
            tasks = self._decode_simple_json(tasks)

        first_task = next((item for item in tasks if isinstance(item, Mapping)), None) if isinstance(tasks, list) else None
        if first_task is not None:
            return {
                "enabled": bool(first_task.get("en")) if first_task.get("en") is not None else None,
                "start": first_task.get("st"),
                "end": first_task.get("et"),
                "tasks": tasks,
                "raw_batch": {"DND_TASK": dnd_task, "DND": dnd},
            }

        raw_dnd = dnd[0] if isinstance(dnd, list) and dnd else dnd
        raw_dnd = self._decode_simple_json(raw_dnd)
        if isinstance(raw_dnd, Mapping):
            return {
                "enabled": raw_dnd.get("enabled") or raw_dnd.get("en"),
                "start": raw_dnd.get("start") or raw_dnd.get("st"),
                "end": raw_dnd.get("end") or raw_dnd.get("et"),
                "tasks": None,
                "raw_batch": {"DND_TASK": dnd_task, "DND": dnd},
            }
        return None

    @staticmethod
    def _parse_dnd_action_response(response: Any) -> dict[str, Any] | None:
        result = response
        if isinstance(response, Mapping):
            if "out" in response:
                result = response
            else:
                data = response.get("data")
                result = response.get("result") or (data.get("result") if isinstance(data, Mapping) else None)
        if not isinstance(result, Mapping):
            return None
        out = result.get("out")
        if not isinstance(out, list):
            return None
        payload = next(
            (item.get("d") for item in out if isinstance(item, Mapping) and isinstance(item.get("d"), Mapping)),
            None,
        )
        if not isinstance(payload, Mapping):
            return None
        start = payload.get("start")
        end = payload.get("end")
        return {
            "enabled": bool(payload.get("value")) if payload.get("value") is not None else None,
            "start": MovaLidaxCoordinator._format_minutes(start),
            "end": MovaLidaxCoordinator._format_minutes(end),
            "start_minutes": start,
            "end_minutes": end,
            "tasks": None,
            "raw_action": result,
        }

    @staticmethod
    def _is_visible_schedule_entry(entry: list[Any]) -> bool:
        """Return true only for schedule slots that still look visible in MOVA Home."""
        enabled = bool(entry[2]) if len(entry) > 2 else False
        if not enabled:
            return False

        # Observed deleted LiDAX schedule slots can keep their enabled bit but
        # flip this second field to 0 while MOVA Home no longer lists them.
        visibility_flag = entry[1] if len(entry) > 1 else None
        if isinstance(visibility_flag, (int, bool)) and int(visibility_flag) <= 0:
            return False

        minutes = entry[3] if len(entry) > 3 else None
        weekdays = entry[4] if len(entry) > 4 else None
        if not isinstance(minutes, int) or not isinstance(weekdays, list) or not weekdays:
            return False
        return True

    def _decode_chunked_json_array(self, response: Mapping[str, Any], prefix: str) -> Any:
        length = response.get(f"{prefix}.info")
        try:
            expected_length = int(length)
        except (TypeError, ValueError):
            return None

        chunks: list[str] = []
        index = 0
        while True:
            key = f"{prefix}.{index}"
            if key not in response:
                break
            value = response.get(key)
            if not isinstance(value, str):
                break
            chunks.append(value)
            index += 1

        if not chunks:
            return None

        raw = "".join(chunks)[:expected_length]
        try:
            return json.loads(raw)
        except Exception:
            LOGGER.debug("Unable to decode chunked batch block %s", prefix, exc_info=True)
            return None

    def _decode_m_path(self, response: Mapping[str, Any]) -> list[dict[str, Any]] | None:
        chunks: list[str] = []
        index = 0
        while True:
            key = f"M_PATH.{index}"
            if key not in response:
                break
            value = response.get(key)
            if not isinstance(value, str):
                break
            chunks.append(value)
            index += 1

        if not chunks:
            return None
        raw = "".join(chunks)
        pair_pattern = re.compile(r"\[\s*(-?\d+)\s*,\s*(-?\d+)\s*\]")
        matches = pair_pattern.findall(raw)
        if not matches:
            return None
        segments: list[list[dict[str, int]]] = []
        current_segment: list[dict[str, int]] = []
        for raw_x, raw_y in matches:
            x = int(raw_x)
            y = int(raw_y)
            if x == 32767 and y == -32768:
                if current_segment:
                    segments.append(current_segment)
                    current_segment = []
                continue
            current_segment.append({"x": x, "y": y})
        if current_segment:
            segments.append(current_segment)
        if not segments:
            return None
        return [
            {
                "map_id": index,
                "map_index": index,
                "points": points,
                "current_position": points[-1] if points else None,
            }
            for index, points in enumerate(segments)
            if points
        ]

    @staticmethod
    def _point_in_boundary(point: Mapping[str, Any] | None, boundary: Mapping[str, Any] | None, tolerance: int = 500) -> bool:
        if not isinstance(point, Mapping) or not isinstance(boundary, Mapping):
            return False
        x = point.get("x")
        y = point.get("y")
        x1 = boundary.get("x1")
        y1 = boundary.get("y1")
        x2 = boundary.get("x2")
        y2 = boundary.get("y2")
        if not all(isinstance(value, (int, float)) for value in (x, y, x1, y1, x2, y2)):
            return False
        return (x1 - tolerance) <= x <= (x2 + tolerance) and (y1 - tolerance) <= y <= (y2 + tolerance)

    @staticmethod
    def _format_minutes(value: Any) -> str | None:
        if not isinstance(value, int):
            return None
        hours, minutes = divmod(value, 60)
        return f"{hours:02d}:{minutes:02d}"

    @staticmethod
    def _format_weekdays(days: Any) -> list[str] | None:
        if not isinstance(days, list):
            return None
        names = {
            0: "Mon",
            1: "Tue",
            2: "Wed",
            3: "Thu",
            4: "Fri",
            5: "Sat",
            6: "Sun",
        }
        return [names.get(day, str(day)) for day in days]
