# Nebula OTA for Home Assistant

> **Beta.** Part of the **Nebula Home** system. This integration hosts
> **Nebula Cosmos UI** firmware updates on your Home Assistant server so the
> panels pull OTAs from your HA instead of `download.lineageos.org`. The rest of
> Nebula lives in [`kamtechsol/nebula-control`](https://github.com/kamtechsol/nebula-control)
> (see `os/COSMOS-UI.md`); the companion HA integration is
> [`kamtechsol/nebula-hass`](https://github.com/kamtechsol/nebula-hass).

It serves the standard LineageOS Updater feed + the signed build zips:

- `GET /api/nebula_ota/{device}` — the update feed (JSON)
- `GET /api/nebula_ota/v1/{device}/{type}/{incr}` — same, LineageOS URL template
- `GET /api/nebula_ota/download/{device}/{filename}` — the zip (supports Range/resume)

All three are unauthenticated (the on-device Updater sends no HA credentials)
and gated only by an optional shared `?token=` secret.

## Install

### HACS (custom repository)

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/kamtechsol/nebula-ota-hass`, category **Integration**.
2. Install **Nebula OTA**, restart Home Assistant.
3. **Settings → Devices & Services → Add Integration → Nebula OTA.**

### Manual

Copy `custom_components/nebula_ota/` into `<config>/custom_components/` and restart.

## Configure

| Field | Default | Notes |
|---|---|---|
| Build directory | `nebula_ota/builds` (under the config dir) | Layout: `builds_dir/<device>/<zip>` |
| Base URL | auto-detect | Used to build the `url` in the feed. Set this if HA can't detect its own external URL. |
| Token | *(blank)* | If set, the feed and downloads require `?token=<value>`. The token is baked into the `url` the feed returns, so the Updater carries it automatically. |
| Channel | `internal` | `romtype` for any zip without a sidecar. |

## Publishing a build

From the build box, after signing (see `nebula-control` →
`os/vendor/nebula/security/README.md`):

```bash
# copy the signed zip into the library
mkdir -p /config/nebula_ota/builds/checkers
cp nebula-cosmos-aether-0.2-checkers.zip /config/nebula_ota/builds/checkers/

# optional sidecar with authoritative metadata (else it's derived)
cat > /config/nebula_ota/builds/checkers/nebula-cosmos-aether-0.2-checkers.zip.json <<'EOF'
{ "version": "0.2", "romtype": "internal", "datetime": 1725400000,
  "id": "<sha256>", "size": 412000000 }
EOF
```

Then either wait 5 minutes or call **`nebula_ota.rescan`**. `vendor/nebula/tools/publish-ota.sh`
can do the copy + sidecar + `scp` for you.

## On the ROM side

`vendor/nebula/overlay/packages/apps/Updater/res/values/strings.xml` sets

```xml
<string name="updater_server_url">https://HASS_HOST/local/nebula-ota/{device}.json</string>
```

Point it at this integration instead:

```xml
<string name="updater_server_url">https://HASS_HOST/api/nebula_ota/v1/{device}/{type}/{incr}</string>
```

(or `.../api/nebula_ota/{device}` — the short form ignores `{type}`/`{incr}`).

## Entities & services

- `sensor.nebula_ota_<device>_latest` — newest version on offer, with
  `filename` / `channel` / `size_mb` / `sha256` / `published` / `count`
  attributes. Trigger a phone notification off a state change.
- `nebula_ota.rescan` — re-read the library now.

## Feed format

```json
{ "response": [ {
  "datetime": 1725400000, "filename": "nebula-cosmos-aether-0.2-checkers.zip",
  "id": "<sha256>", "romtype": "internal", "size": 412000000,
  "url": "https://HASS_HOST/api/nebula_ota/download/checkers/nebula-cosmos-aether-0.2-checkers.zip",
  "version": "0.2"
} ] }
```

Newest first. The Updater offers any entry whose `datetime` is newer than the
running build.
