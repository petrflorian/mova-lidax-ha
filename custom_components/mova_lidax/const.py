"""Constants for the MOVA LiDAX integration."""

from __future__ import annotations

import logging

DOMAIN = "mova_lidax"
LOGGER = logging.getLogger(__package__)

CONF_COUNTRY = "country"
CONF_DID = "did"
CONF_ACCOUNT_TYPE = "account_type"
CONF_MAC = "mac"
CONF_MODEL = "model"

DEFAULT_COUNTRY = "eu"
DEFAULT_ACCOUNT_TYPE = "mova"

SERVICE_SWITCH_MAP = "switch_map"
SERVICE_SCHEDULE_CONFIG = "schedule_config"
SERVICE_UPDATE_SCHEDULE = "update_schedule"
SERVICE_RAW_ACTION = "raw_action"

ATTR_MAP_ID = "map_id"
ATTR_MAP_INDEX = "map_index"
MAX_SCHEDULE_SLOTS = 3
ENABLE_DEBUG_SNAPSHOT = False

EXTRA_BATCH_KEYS = (
    "MAP.info",
    *[f"MAP.{index}" for index in range(32)],
    "M_PATH.info",
    *[f"M_PATH.{index}" for index in range(32)],
    "SCHEDULE_TASK.info",
    "SCHEDULE_TASK.0",
    "DND_TASK.info",
    "DND_TASK.0",
    "DND.info",
    "DND.0",
    "AI_OBS.info",
    "AI_OBS.0",
    "PATH.info",
    "PATH.0",
    "FBD_NTYPE.info",
    "FBD_NTYPE.0",
    "TASKID.info",
    "TASKID.0",
    "CRUISE.info",
    "CRUISE.0",
    "OTA_INFO.info",
    "OTA_INFO.0",
)
