# Changelog

## 0.1.3

Branding update.

- Add local Home Assistant brand assets in `brand/icon.png` and `brand/logo.png`.
- Add the MOVA logo to the built-in sidebar panel.
- Serve frontend panel assets from the integration static directory.

## 0.1.2

Fix HACS release ZIP layout so `manifest.json` is extracted directly into
`/config/custom_components/mova_lidax`.

## 0.1.1

Packaging and production UX cleanup.

- Vendor the patched Dreame/MOVA transport inside `mova_lidax`.
- Remove the separate top-level `dreame_mower` custom component from the HACS package.
- Add a built-in `MOVA LiDAX` sidebar panel.
- Remove the need to edit Lovelace YAML for the default dashboard.

## 0.1.0

Initial production candidate.

- Add MOVA cloud login and LiDAX mower discovery.
- Add main mower entity.
- Add start, pause and dock controls.
- Add saved map select and LiDAX map switching.
- Add battery, state and task status sensors.
- Add Do Not Disturb read-only sensors.
- Add current mowing progress sensors.
- Add read-only mowing history.
- Add read-only schedule overview.
- Include patched `dreame_mower` transport dependency.
