"""Resilient backup/restore engine.

Design goals (see spec):
  * Backups leave the Docker volume entirely — they land on bind-mounted host
    folders (primary disk + best-effort removable drive).
  * The backup dump is never written to local plaintext disk: pg_dump streams
    to memory, is encrypted, then written straight to the destination(s).
  * The list of backups is read from the destinations' manifest files, so it
    survives total loss of this database.
"""
import hashlib
import json
import logging
import subprocess
from datetime import UTC, datetime

from django.conf import settings

from .crypto import decrypt_bytes, encrypt_bytes
from .destinations import LocalPathDestination
from .models import BackupConfig

logger = logging.getLogger("apps.backups")

# pg_dump custom-format archives start with the magic bytes "PGDMP".
PGDUMP_MAGIC = b"PGDMP"


# ---------------------------------------------------------------------------
# Postgres helpers
# ---------------------------------------------------------------------------
def _db():
    cfg = settings.DATABASES["default"]
    if "postgresql" not in cfg["ENGINE"]:
        raise RuntimeError("Backups require PostgreSQL (pg_dump/pg_restore).")
    return cfg


def _conn_args(cfg):
    return [
        "-h", str(cfg.get("HOST") or "localhost"),
        "-p", str(cfg.get("PORT") or 5432),
        "-U", str(cfg["USER"]),
    ]


def _pg_env(cfg):
    import os

    env = os.environ.copy()
    env["PGPASSWORD"] = str(cfg.get("PASSWORD") or "")
    return env


def make_dump() -> bytes:
    """Run pg_dump -Fc and return the archive bytes (no local plaintext file)."""
    cfg = _db()
    cmd = [settings.PG_DUMP_BIN, *_conn_args(cfg), "-Fc", "-d", cfg["NAME"]]
    proc = subprocess.run(cmd, capture_output=True, env=_pg_env(cfg))
    if proc.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {proc.stderr.decode(errors='replace')[:500]}")
    return proc.stdout


def restore_dump(dump_bytes: bytes):
    """pg_restore the archive over the live DB atomically (single transaction)."""
    cfg = _db()
    cmd = [
        settings.PG_RESTORE_BIN, *_conn_args(cfg),
        "--clean", "--if-exists", "--no-owner", "--no-privileges",
        "--single-transaction", "-d", cfg["NAME"],
    ]
    proc = subprocess.run(cmd, input=dump_bytes, capture_output=True, env=_pg_env(cfg))
    if proc.returncode != 0:
        raise RuntimeError(f"pg_restore failed: {proc.stderr.decode(errors='replace')[:800]}")


# ---------------------------------------------------------------------------
# Destinations
# ---------------------------------------------------------------------------
def _config(shop):
    cfg, _ = BackupConfig.objects.get_or_create(shop=shop)
    return cfg


def _destinations(shop):
    cfg = _config(shop)
    primary = LocalPathDestination("primary", cfg.primary_path or settings.BACKUP_PRIMARY_PATH)
    secondary = LocalPathDestination("secondary", cfg.secondary_path or settings.BACKUP_SECONDARY_PATH)
    return primary, secondary


def _timestamp_name():
    import secrets

    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return f"backup_{ts}_{secrets.token_hex(3)}.dump.enc"


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------
def _store(shop, encrypted: bytes, source: str, filename=None):
    """Write already-encrypted bytes to primary (required) + secondary
    (best-effort), then write a manifest to each destination that succeeded."""
    filename = filename or _timestamp_name()
    primary, secondary = _destinations(shop)

    ok, reason = primary.available(create=True)
    if not ok:
        raise RuntimeError(f"Primary backup destination unavailable: {reason}")
    primary.write(filename, encrypted)

    dest_status = {"primary": True, "secondary": False}
    sec_ok, sec_reason = secondary.available()
    if sec_ok:
        try:
            secondary.write(filename, encrypted)
            dest_status["secondary"] = True
        except OSError as exc:  # pragma: no cover
            dest_status["secondary_reason"] = str(exc)
            logger.warning("secondary backup write failed: %s", exc)
    else:
        dest_status["secondary_reason"] = sec_reason or "drive not attached"
        logger.info("secondary backup skipped — %s", dest_status["secondary_reason"])

    manifest = {
        "filename": filename,
        "timestamp": datetime.now(UTC).isoformat(),
        "size": len(encrypted),
        "checksum_sha256": hashlib.sha256(encrypted).hexdigest(),
        "source": source,
        "app_sha": settings.APP_GIT_SHA,
        "encrypted": True,
        "destinations": dest_status,
    }
    manifest_json = json.dumps(manifest, indent=2)
    primary.write_manifest(filename, manifest_json)
    if dest_status["secondary"]:
        secondary.write_manifest(filename, manifest_json)

    return manifest


def run_backup(shop, source="scheduled"):
    """Full backup: dump -> encrypt -> write to destinations -> manifest."""
    encrypted = encrypt_bytes(make_dump())
    manifest = _store(shop, encrypted, source=source)
    cfg = _config(shop)
    from django.utils import timezone as djtz

    cfg.last_run_at = djtz.now()
    cfg.save(update_fields=["last_run_at"])
    return manifest


# ---------------------------------------------------------------------------
# Manual upload
# ---------------------------------------------------------------------------
def looks_like_pgdump(data: bytes) -> bool:
    return data[:5] == PGDUMP_MAGIC


def ingest_upload(shop, raw: bytes, already_encrypted: bool):
    """Validate + store an externally-provided dump. Plain dumps are encrypted
    on the way in; .enc files are validated by decrypting first."""
    if already_encrypted:
        try:
            plain = decrypt_bytes(raw)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("Could not decrypt the uploaded .enc file with the master key.") from exc
    else:
        plain = raw
    if not looks_like_pgdump(plain):
        raise RuntimeError("Not a valid pg_dump custom-format archive (bad header).")
    encrypted = raw if already_encrypted else encrypt_bytes(plain)
    return _store(shop, encrypted, source="manual_upload")


# ---------------------------------------------------------------------------
# Storage-sourced listing (survives DB loss)
# ---------------------------------------------------------------------------
def list_backups(shop):
    primary, secondary = _destinations(shop)
    merged = {}
    for dest in (primary, secondary):
        for raw in dest.list_manifests():
            try:
                m = json.loads(raw)
            except ValueError:
                continue
            fn = m.get("filename")
            if not fn:
                continue
            if fn in merged:
                # Merge destination presence across the two locations.
                d = merged[fn]["destinations"]
                d2 = m.get("destinations", {})
                d["primary"] = d.get("primary") or d2.get("primary", False)
                d["secondary"] = d.get("secondary") or d2.get("secondary", False)
            else:
                merged[fn] = m
    return sorted(merged.values(), key=lambda m: m.get("timestamp", ""), reverse=True)


def find_backup_bytes(shop, filename):
    """Read the encrypted bytes for a filename from whichever destination has it."""
    primary, secondary = _destinations(shop)
    for dest in (primary, secondary):
        if dest.exists(filename):
            return dest.read(filename)
    raise RuntimeError(f"Backup file not found at any destination: {filename}")


# ---------------------------------------------------------------------------
# Restore
# ---------------------------------------------------------------------------
def perform_restore(shop, filename, user):
    """Mandatory pre-restore safety backup, then restore in-place atomically.
    Returns (safety_filename, RestoreAudit)."""
    from .models import RestoreAudit

    # 1. Non-skippable safety net of the CURRENT state.
    safety = run_backup(shop, source="pre_restore_safety")
    safety_name = safety["filename"]

    try:
        encrypted = find_backup_bytes(shop, filename)
        dump = decrypt_bytes(encrypted)
        if not looks_like_pgdump(dump):
            raise RuntimeError("Decrypted archive is not a valid pg_dump file.")
        restore_dump(dump)  # atomic: --single-transaction
        audit = RestoreAudit.objects.create(
            shop=shop, performed_by=user, backup_filename=filename,
            safety_backup_filename=safety_name, status=RestoreAudit.Status.SUCCESS,
            message="Restored in-place (single transaction).",
        )
        return safety_name, audit
    except Exception as exc:  # noqa: BLE001
        RestoreAudit.objects.create(
            shop=shop, performed_by=user, backup_filename=filename,
            safety_backup_filename=safety_name, status=RestoreAudit.Status.FAILED,
            message=str(exc)[:1000],
        )
        raise
