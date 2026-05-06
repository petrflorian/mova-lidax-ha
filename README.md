# MOVA LiDAX for Home Assistant

Custom Home Assistant integration for MOVA LiDAX Ultra mowers.

Current version: `0.1.0`

## Status

This is an early production build for one known MOVA LiDAX Ultra setup.

Works:

- MOVA cloud login and mower discovery
- Main `lawn_mower` entity
- Start, pause and dock actions
- Battery, state and task status
- Active saved map selection
- Two-map switching used by LiDAX Ultra
- Saved map names, area and zone count
- Do Not Disturb read-only state and time window
- Current mowing progress, mowed area and target area
- Read-only mowing history from cloud event `4.1`
- Read-only schedule overview

Known limits:

- Cloud only; local LAN control is not implemented.
- Live mower position is not production-ready yet.
- Video feed is not implemented.
- Schedule editing should stay in the MOVA app for now.

## HACS Install

1. Open HACS in Home Assistant.
2. Go to `Integrations`.
3. Open `Custom repositories`.
4. Add this repository URL.
5. Select category `Integration`.
6. Install `MOVA LiDAX`.
7. Restart Home Assistant.
8. Add `MOVA LiDAX` from `Settings -> Devices & services`.

Use:

- Region: `eu`
- Account type: `mova`

## Manual Install

Copy both folders into your Home Assistant config:

```text
custom_components/dreame_mower -> /config/custom_components/dreame_mower
custom_components/mova_lidax -> /config/custom_components/mova_lidax
```

Restart Home Assistant and add `MOVA LiDAX`.

## Optional Dashboard

Copy:

```text
dashboard/mova_lidax.yaml -> /config/dashboards/mova_lidax.yaml
```

Add to `configuration.yaml`:

```yaml
lovelace:
  dashboards:
    mova-lidax:
      mode: yaml
      title: MOVA LiDAX
      icon: mdi:robot-mower
      show_in_sidebar: true
      filename: dashboards/mova_lidax.yaml
```

Restart Home Assistant after changing `configuration.yaml`.

## Updating

If installed through HACS, update from HACS and restart Home Assistant.

If installed manually:

```bash
cd /config
git pull
```

or copy the latest release files over the old `custom_components` folders and restart Home Assistant.

## Included Dependency

This repository includes a patched copy of `dreame_mower` because `mova_lidax` currently reuses its MOVA/Dreame cloud transport.

Original project:

```text
https://github.com/bhuebschen/dreame-mower
```

## Production Notes

See:

```text
docs/PRODUCTION_0_1.md
```

