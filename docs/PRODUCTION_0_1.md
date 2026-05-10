# MOVA LiDAX 0.1 Production Checklist

Checklist for build `0.1.3`.

## HACS Install

1. Add this repository as a HACS custom repository:

```text
https://github.com/petrflorian/mova-lidax-ha
```

2. Category:

```text
Integration
```

3. Install `MOVA LiDAX`.
4. Restart Home Assistant.
5. Add `MOVA LiDAX` from `Settings -> Devices & services`.
6. Use region `eu` and account type `mova`.
7. Open `MOVA LiDAX` in the sidebar.

## Manual Install

Copy one folder into Home Assistant:

```text
custom_components/mova_lidax -> /config/custom_components/mova_lidax
```

Restart Home Assistant and add the integration.

Do not copy or install a separate `dreame_mower` folder. The required transport is vendored inside `mova_lidax/dreame`.

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

## Expected UI

The integration registers a `MOVA LiDAX` sidebar panel.

No manual Lovelace YAML, dashboard copy step, or `configuration.yaml` change is required.

## Known 0.1 Limits

- Cloud only.
- No production live position marker.
- No video feed.
- Schedule editing stays in MOVA app.
- DND editing stays in MOVA app.
