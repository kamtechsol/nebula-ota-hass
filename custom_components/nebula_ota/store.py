"""Build library for Nebula OTA.

Scans `<builds_dir>/<device>/*.zip` and turns each zip into a `Build` with the
metadata the LineageOS Updater wants. Metadata comes from a `<name>.zip.json`
sidecar when present (written by publish-ota.sh), otherwise it is derived from
the filename + stat, with the sha256 computed once and cached.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path

from homeassistant.core import HomeAssistant

from .const import CACHE_FILE, DEFAULT_CHANNEL, FILENAME_RE

_LOGGER = logging.getLogger(__name__)
_FN = re.compile(FILENAME_RE)


@dataclass(slots=True)
class Build:
    device: str
    filename: str
    path: str
    size: int
    datetime: int
    version: str
    romtype: str
    sha256: str

    def as_feed_entry(self, base_url: str, token: str | None) -> dict:
        url = f"{base_url}/api/nebula_ota/download/{self.device}/{self.filename}"
        if token:
            url = f"{url}?token={token}"
        return {
            "datetime": self.datetime,
            "filename": self.filename,
            "id": self.sha256,
            "romtype": self.romtype,
            "size": self.size,
            "url": url,
            "version": self.version,
        }


class BuildStore:
    """In-memory catalog of everything under `builds_dir`."""

    def __init__(self, hass: HomeAssistant, builds_dir: str, default_channel: str) -> None:
        self._hass = hass
        self._root = Path(builds_dir)
        self._default_channel = default_channel or DEFAULT_CHANNEL
        self._builds: dict[str, list[Build]] = {}  # device -> newest-first
        self._cache: dict[str, dict] = {}
        self._last_scan = 0.0

    # ------------------------------------------------------------------ scan

    async def async_scan(self) -> bool:
        """Rescan the library. Returns True if the catalog changed."""
        before = self._signature()
        self._builds = await self._hass.async_add_executor_job(self._scan_blocking)
        self._last_scan = time.monotonic()
        return self._signature() != before

    def _signature(self) -> tuple:
        return tuple(
            (dev, b.filename, b.size, b.datetime)
            for dev, lst in sorted(self._builds.items())
            for b in lst
        )

    def _scan_blocking(self) -> dict[str, list[Build]]:
        self._root.mkdir(parents=True, exist_ok=True)
        self._load_cache()
        out: dict[str, list[Build]] = {}

        for dev_dir in sorted(p for p in self._root.iterdir() if p.is_dir()):
            device = dev_dir.name
            builds: list[Build] = []
            for zp in sorted(dev_dir.glob("*.zip")):
                try:
                    builds.append(self._build_for(device, zp))
                except OSError as err:  # noqa: PERF203
                    _LOGGER.warning("nebula_ota: skipping %s (%s)", zp, err)
            if builds:
                builds.sort(key=lambda b: b.datetime, reverse=True)
                out[device] = builds

        self._save_cache()
        total = sum(len(v) for v in out.values())
        _LOGGER.debug("nebula_ota: %d build(s) across %d device(s) in %s",
                      total, len(out), self._root)
        return out

    def _build_for(self, device: str, zp: Path) -> Build:
        st = zp.stat()
        size, mtime = st.st_size, int(st.st_mtime)
        meta = self._sidecar(zp)

        sha = meta.get("id") or meta.get("sha256")
        cached = self._cache.get(zp.name)
        if not sha:
            if cached and cached.get("size") == size and cached.get("mtime") == mtime:
                sha = cached["sha256"]
            else:
                sha = _sha256(zp)
        self._cache[zp.name] = {"size": size, "mtime": mtime, "sha256": sha}

        m = _FN.match(zp.name)
        version = meta.get("version") or (m.group("version") if m else time.strftime(
            "%Y%m%d", time.localtime(mtime)))
        return Build(
            device=device,
            filename=zp.name,
            path=str(zp),
            size=int(meta.get("size") or size),
            datetime=int(meta.get("datetime") or mtime),
            version=version,
            romtype=str(meta.get("romtype") or self._default_channel),
            sha256=sha,
        )

    @staticmethod
    def _sidecar(zp: Path) -> dict:
        side = zp.with_suffix(zp.suffix + ".json")
        if not side.is_file():
            return {}
        try:
            data = json.loads(side.read_text())
        except (OSError, ValueError):
            return {}
        # accept either a bare object or a LineageOS {"response":[{...}]}
        if isinstance(data, dict) and isinstance(data.get("response"), list) and data["response"]:
            return data["response"][0]
        return data if isinstance(data, dict) else {}

    def _load_cache(self) -> None:
        f = self._root / CACHE_FILE
        try:
            self._cache = json.loads(f.read_text()) if f.is_file() else {}
        except (OSError, ValueError):
            self._cache = {}

    def _save_cache(self) -> None:
        try:
            (self._root / CACHE_FILE).write_text(json.dumps(self._cache, indent=0))
        except OSError:
            pass

    # --------------------------------------------------------------- queries

    def devices(self) -> list[str]:
        return sorted(self._builds)

    def builds_for(self, device: str, channel: str | None = None) -> list[Build]:
        builds = self._builds.get(device, [])
        if channel and channel.lower() not in ("nightly", "unofficial", ""):
            matched = [b for b in builds if b.romtype.lower() == channel.lower()]
            if matched:
                return matched
            if builds:
                _LOGGER.debug(
                    "nebula_ota: no %s builds for %s; serving all %d",
                    channel, device, len(builds),
                )
        return builds

    def latest(self, device: str, channel: str | None = None) -> Build | None:
        b = self.builds_for(device, channel)
        return b[0] if b else None

    def get(self, device: str, filename: str) -> Build | None:
        if "/" in filename or "\\" in filename or filename.startswith("."):
            return None
        for b in self._builds.get(device, []):
            if b.filename == filename:
                return b
        return None

    @property
    def root(self) -> Path:
        return self._root


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
