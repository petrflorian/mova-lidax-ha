# MOVA LiDAX 0.1 Production Checklist

This is the production handoff checklist for the local `0.1.0` build.

## Build Release Package

```bash
cd /Users/petr/Projects/mova
./scripts/build-mova-lidax-release.sh
```

Output:

```text
/Users/petr/Projects/mova/dist/mova-lidax-0.1.0
```

## Copy To Production HA

Copy these folders into production Home Assistant:

```text
dist/mova-lidax-0.1.0/custom_components/dreame_mower -> /config/custom_components/dreame_mower
dist/mova-lidax-0.1.0/custom_components/mova_lidax -> /config/custom_components/mova_lidax
```

Optional dashboard:

```text
dist/mova-lidax-0.1.0/dashboard/mova_lidax.yaml -> /config/dashboards/mova_lidax.yaml
```

## Restart And Add Integration

1. Restart Home Assistant.
2. Go to `Settings -> Devices & services`.
3. Add `MOVA LiDAX`.
4. Login with MOVA cloud account.
5. Select the LiDAX mower.

## First Validation

Check that these entities exist and are not broken:

- `lawn_mower.lidax_ultra_2`
- `select.lidax_ultra`
- `sensor.lidax_ultra`
- `sensor.lidax_ultra_2`
- `sensor.lidax_ultra_task_status`
- `sensor.lidax_ultra_do_not_disturb`
- `sensor.lidax_ultra_current_mowing_progress`
- `sensor.lidax_ultra_mowing_history`

Entity IDs may differ if production HA already has similarly named entities.

## Known 0.1 Limits

- Cloud only.
- No production live position marker.
- No video feed.
- Schedule editing stays in MOVA app.
- Dashboard YAML currently assumes the common entity IDs from the dev instance.

