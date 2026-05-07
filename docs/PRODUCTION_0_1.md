# MOVA LiDAX 0.1 Production Checklist

This is the production handoff checklist for the `0.1.1` build.

## HACS Install

1. Add `https://github.com/petrflorian/mova-lidax-ha` as a HACS custom repository.
2. Category: `Integration`.
3. Install `MOVA LiDAX`.
4. Restart Home Assistant.
5. Add `MOVA LiDAX` from `Settings -> Devices & services`.
6. Open `MOVA LiDAX` in the sidebar.

## Manual Install

Copy this folder into Home Assistant:

```text
custom_components/mova_lidax -> /config/custom_components/mova_lidax
```

Restart Home Assistant and add the integration.

## First Validation

Check that these entities exist and are not broken:

- `lawn_mower.lidax_ultra`
- `select.lidax_ultra`
- `sensor.lidax_ultra`
- `sensor.lidax_ultra_state`
- `sensor.lidax_ultra_task_status`
- `sensor.lidax_ultra_do_not_disturb`
- `sensor.lidax_ultra_current_mowing_progress`
- `sensor.lidax_ultra_mowing_history`

Entity IDs may differ if production HA already has similarly named entities. The built-in panel tries to find suffixed LiDAX entities automatically.

## Known 0.1 Limits

- Cloud only.
- No production live position marker.
- No video feed.
- Schedule editing stays in MOVA app.
