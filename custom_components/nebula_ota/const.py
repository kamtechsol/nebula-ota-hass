"""Constants for the Nebula OTA integration."""

DOMAIN = "nebula_ota"

DATA_STORE = "store"
DATA_UNSUB = "unsub"
DATA_HTTP_REGISTERED = "_http_registered"
DATA_SENSOR_ADD = "sensor_add"
DATA_SENSOR_SEEN = "sensor_seen"

# Config-entry keys (stored in .data, editable via the options flow).
CONF_BUILDS_DIR = "builds_dir"
CONF_BASE_URL = "base_url"
CONF_TOKEN = "token"
CONF_CHANNEL = "channel"

# Default build library, relative to the HA config dir.
DEFAULT_BUILDS_DIR = "nebula_ota/builds"
DEFAULT_CHANNEL = "internal"

# HTTP routes. The LineageOS Updater hits these UNAUTHENTICATED, so the views
# are `requires_auth = False` and gated only by the optional `?token=` secret.
#   {device}     -> ro.lineage.device        (e.g. checkers)
#   {build_type} -> ro.lineage.releasetype   (lowercased; our channel)
#   {incr}       -> ro.build.version.incremental   (ignored; we serve full zips)
FEED_URL = "/api/nebula_ota/v1/{device}/{build_type}/{incr}"
FEED_URL_EXTRA = (
    "/api/nebula_ota/v1/{device}/{build_type}",
    "/api/nebula_ota/{device}",
)
DOWNLOAD_URL = "/api/nebula_ota/download/{device}/{filename}"

# Filename convention written by vendor/nebula/tools/publish-ota.sh:
#   nebula-cosmos-aether-<version>-<device>.zip
FILENAME_RE = r"^nebula-cosmos-aether-(?P<version>.+)-(?P<device>[a-z0-9_]+)\.zip$"

SCAN_INTERVAL = 300  # seconds between automatic library rescans
CACHE_FILE = ".nebula_ota_cache.json"  # sha256 cache inside builds_dir

SIGNAL_BUILDS_CHANGED = f"{DOMAIN}_builds_changed"
