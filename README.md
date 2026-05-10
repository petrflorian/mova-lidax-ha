# MOVA LiDAX for Home Assistant

Custom Home Assistant integration for MOVA LiDAX Ultra mowers.

Current version: `0.1.3`

This is an early production build for one known MOVA LiDAX Ultra setup. It is cloud-only and currently focuses on reliable monitoring, map switching, current mowing progress and mowing history.

## Works

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
- Built-in `MOVA LiDAX` sidebar panel

## Known Limits

- Cloud only; local LAN control is not implemented.
- Live mower position is not production-ready yet.
- Video feed is not implemented.
- Schedule editing should stay in the MOVA app for now.
- DND editing should stay in the MOVA app for now.

## HACS Install

1. Open HACS in Home Assistant.
2. Go to `Integrations`.
3. Open `Custom repositories`.
4. Add this repository URL:

```text
https://github.com/petrflorian/mova-lidax-ha
```

5. Select category `Integration`.
6. Install `MOVA LiDAX`.
7. Restart Home Assistant.
8. Add `MOVA LiDAX` from `Settings -> Devices & services`.
9. Open `MOVA LiDAX` in the sidebar.

Use:

- Region: `eu`
- Account type: `mova`

## Manual Install

Copy the integration folder into your Home Assistant config:

```text
custom_components/mova_lidax -> /config/custom_components/mova_lidax
```

Restart Home Assistant and add `MOVA LiDAX`.

Do not install a separate `dreame_mower` custom component for this integration. The required patched MOVA/Dreame transport is vendored inside `custom_components/mova_lidax/dreame`.

## Dashboard

The integration registers its own `MOVA LiDAX` sidebar panel. No manual Lovelace YAML or `configuration.yaml` changes are required.

## Updating

If installed through HACS, update from HACS and restart Home Assistant.

If installed manually, copy the latest release files over the old `custom_components/mova_lidax` folder and restart Home Assistant.

## Included Dependency

This repository includes a vendored copy of the patched Dreame/MOVA transport inside:

```text
custom_components/mova_lidax/dreame
```

Original project:

```text
https://github.com/bhuebschen/dreame-mower
```

## Production Notes

See:

```text
docs/PRODUCTION_0_1.md
```
