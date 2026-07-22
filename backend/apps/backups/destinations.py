"""Backup destinations.

A destination is anything that can accept a "write this backup here" request.
Today only local filesystem paths are implemented (primary disk folder +
best-effort removable drive), but the contract is deliberately generic so a
cloud bucket is a drop-in third implementation later — no redesign needed.

Windows-style host paths (e.g. ``D:\\SecureBackups``) that staff type in the UI
are resolved to the container mount point via ``settings.BACKUP_PATH_MAP`` so
the Linux container can actually write to the bind-mounted folder.
"""
import os
import shutil
from pathlib import PurePath

from django.conf import settings


def resolve_path(configured: str) -> str:
    """Translate a (possibly Windows) host path to a writable local path.

    1. If the path exists as-is (e.g. command run on the host), use it.
    2. Otherwise apply the longest matching prefix from BACKUP_PATH_MAP to map
       a host path to its container bind-mount.
    3. Otherwise return it unchanged (caller handles unreachable).
    """
    if not configured:
        return ""
    if os.path.isdir(configured):
        return configured
    norm = configured.replace("\\", "/").rstrip("/")
    best = None
    for host_prefix, container_path in settings.BACKUP_PATH_MAP.items():
        hp = host_prefix.replace("\\", "/").rstrip("/")
        if norm.lower() == hp.lower() or norm.lower().startswith(hp.lower() + "/"):
            if best is None or len(hp) > len(best[0]):
                remainder = norm[len(hp):].lstrip("/")
                mapped = str(PurePath(container_path) / remainder) if remainder else container_path
                best = (hp, mapped)
    if best:
        return best[1]
    return configured


class BackupDestination:
    """Contract: write bytes + a sibling manifest; list manifests; read a file."""

    name = "base"

    def available(self) -> tuple[bool, str]:
        raise NotImplementedError

    def write(self, filename: str, data: bytes) -> None:
        raise NotImplementedError

    def write_manifest(self, filename: str, manifest_json: str) -> None:
        raise NotImplementedError

    def list_manifests(self) -> list[str]:
        raise NotImplementedError

    def read(self, filename: str) -> bytes:
        raise NotImplementedError


class LocalPathDestination(BackupDestination):
    def __init__(self, name: str, configured_path: str):
        self.name = name
        self.configured_path = configured_path
        self.path = resolve_path(configured_path)

    def available(self, create: bool = False) -> tuple[bool, str]:
        """Is this destination reachable and writable?

        ``create=True`` (primary) will create the folder if missing. For the
        secondary/removable drive we pass ``create=False`` — the folder must
        already exist, otherwise a detached drive would silently be recreated
        inside the container instead of failing over as intended.
        """
        if not self.path:
            return False, "no path configured"
        if create:
            try:
                os.makedirs(self.path, exist_ok=True)
            except OSError as exc:
                return False, f"cannot create ({exc.__class__.__name__})"
        if not os.path.isdir(self.path):
            return False, "drive not attached"
        try:
            testfile = os.path.join(self.path, ".write_test")
            with open(testfile, "w") as f:
                f.write("ok")
            os.remove(testfile)
            return True, ""
        except OSError as exc:
            return False, f"not writable ({exc.__class__.__name__})"

    def _full(self, filename: str) -> str:
        return os.path.join(self.path, filename)

    def write(self, filename: str, data: bytes) -> None:
        with open(self._full(filename), "wb") as f:
            f.write(data)

    def copy_from(self, src_path: str, filename: str) -> None:
        shutil.copyfile(src_path, self._full(filename))

    def write_manifest(self, filename: str, manifest_json: str) -> None:
        with open(self._full(filename + ".manifest.json"), "w", encoding="utf-8") as f:
            f.write(manifest_json)

    def list_manifests(self) -> list[str]:
        if not self.path or not os.path.isdir(self.path):
            return []
        out = []
        for name in os.listdir(self.path):
            if name.endswith(".manifest.json"):
                with open(os.path.join(self.path, name), encoding="utf-8") as f:
                    out.append(f.read())
        return out

    def read(self, filename: str) -> bytes:
        with open(self._full(filename), "rb") as f:
            return f.read()

    def exists(self, filename: str) -> bool:
        return bool(self.path) and os.path.isfile(self._full(filename))
