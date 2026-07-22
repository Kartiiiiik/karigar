import { useRef, useState } from "react";
import { useForm } from "react-hook-form";
import {
  DatabaseBackup, Play, ShieldAlert, RefreshCw, Upload, RotateCcw,
  HardDrive, Usb, CheckCircle2, XCircle,
} from "lucide-react";
import api, { apiError } from "../lib/api";
import { useFetch } from "../hooks/useFetch";
import { PageHeader, Spinner, EmptyState, ErrorState, Field, Badge, Modal } from "../components/ui";
import { formatDate } from "../lib/date";
import { useSettingsStore } from "../store/settings";
import { useAuthStore } from "../store/auth";

function humanSize(bytes) {
  const n = Number(bytes || 0);
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

const SOURCE_TONE = {
  scheduled: "blue",
  manual: "gray",
  manual_upload: "amber",
  pre_restore_safety: "green",
};

export default function Backups() {
  const calendar = useSettingsStore((s) => s.calendar);
  const dateFormat = useSettingsStore((s) => s.dateFormat);
  const isOwner = useAuthStore((s) => s.user?.role === "owner");

  const config = useFetch("/backups/config/");
  const list = useFetch("/backups/");
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [restoreTarget, setRestoreTarget] = useState(null);
  const fileRef = useRef(null);

  const refreshAll = () => { list.refresh(); config.refresh(); };

  const runNow = async () => {
    setBusy("run"); setMsg(""); setError("");
    try {
      const { data } = await api.post("/backups/run/");
      setMsg(data.detail + (data.filename ? ` (${data.filename})` : ""));
      setTimeout(refreshAll, 1200);
    } catch (e) { setError(apiError(e)); } finally { setBusy(""); }
  };

  const onUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy("upload"); setMsg(""); setError("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("encrypted", String(file.name.endsWith(".enc")));
      const { data } = await api.post("/backups/upload/", fd);
      setMsg(`Uploaded: ${data.filename}`);
      list.refresh();
    } catch (e2) {
      setError(apiError(e2));
    } finally {
      setBusy("");
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const items = list.data ?? [];

  return (
    <div className="max-w-4xl space-y-6">
      <PageHeader
        title="Backups"
        subtitle="Encrypted backups written to storage that survives Docker/DB loss."
        actions={
          <div className="flex gap-2">
            <button className="btn-secondary" disabled={busy === "upload"} onClick={() => fileRef.current?.click()}>
              {busy === "upload" ? <RefreshCw size={16} className="animate-spin" /> : <Upload size={16} />} Upload
            </button>
            <button className="btn-primary" disabled={busy === "run"} onClick={runNow}>
              {busy === "run" ? <RefreshCw size={16} className="animate-spin" /> : <Play size={16} />} Backup now
            </button>
            <input ref={fileRef} type="file" accept=".dump,.enc,.dump.enc" className="hidden" onChange={onUpload} />
          </div>
        }
      />

      <div className="flex items-start gap-2 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800">
        <ShieldAlert size={18} className="mt-0.5 shrink-0" />
        <span>
          Backups are AES-encrypted with a master key held in the server
          environment — the key is never stored in the database or emailed.
          Keep it in your secrets manager; without it, backups cannot be restored.
        </span>
      </div>

      {msg && <p className="text-sm text-green-600">{msg}</p>}
      {error && <ErrorState message={error} />}

      {/* Destinations + schedule */}
      {config.loading ? <Spinner /> : config.data && <ConfigForm data={config.data} onSaved={config.refresh} />}

      {/* Recent backups (from storage manifests) */}
      <div className="card">
        <h2 className="mb-3 flex items-center gap-2 font-semibold text-gray-900">
          <DatabaseBackup size={18} /> Recent backups
        </h2>
        {list.error && <ErrorState message={list.error} />}
        {list.loading ? (
          <Spinner />
        ) : items.length === 0 ? (
          <EmptyState message="No backups found at the destinations yet." />
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full whitespace-nowrap text-sm">
              <thead className="text-left text-xs uppercase text-gray-400">
                <tr>
                  <th className="py-2 pr-3">When</th>
                  <th className="py-2 pr-3">Source</th>
                  <th className="py-2 pr-3">Size</th>
                  <th className="py-2 pr-3">Destinations</th>
                  <th className="py-2 pr-3">Checksum</th>
                  {isOwner && <th className="py-2"></th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {items.map((b) => (
                  <tr key={b.filename}>
                    <td className="py-2 pr-3">{formatDate(b.timestamp, calendar, { format: dateFormat, withTime: true })}</td>
                    <td className="py-2 pr-3">
                      <Badge tone={SOURCE_TONE[b.source] || "gray"}>{b.source.replace(/_/g, " ")}</Badge>
                    </td>
                    <td className="py-2 pr-3">{humanSize(b.size)}</td>
                    <td className="py-2 pr-3">
                      <span className="flex items-center gap-3">
                        <DestBadge ok={b.destinations?.primary} icon={HardDrive} label="Disk" />
                        <DestBadge ok={b.destinations?.secondary} icon={Usb} label="Drive"
                          reason={b.destinations?.secondary_reason} />
                      </span>
                    </td>
                    <td className="py-2 pr-3 font-mono text-xs text-gray-400">{(b.checksum_sha256 || "").slice(0, 10)}…</td>
                    {isOwner && (
                      <td className="py-2 text-right">
                        <button className="btn-secondary py-1" onClick={() => setRestoreTarget(b)}>
                          <RotateCcw size={14} /> Restore
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <RestoreAudits />

      {restoreTarget && (
        <RestoreModal
          backup={restoreTarget}
          calendar={calendar}
          dateFormat={dateFormat}
          onClose={() => setRestoreTarget(null)}
          onDone={(text) => { setRestoreTarget(null); setMsg(text); refreshAll(); }}
        />
      )}
    </div>
  );
}

function DestBadge({ ok, icon: Icon, label, reason }) {
  return (
    <span className={`inline-flex items-center gap-1 text-xs ${ok ? "text-green-700" : "text-gray-400"}`}
      title={!ok && reason ? reason : label}>
      <Icon size={13} />
      {ok ? <CheckCircle2 size={12} /> : <XCircle size={12} />}
      {label}
    </span>
  );
}

function ConfigForm({ data, onSaved }) {
  const { register, handleSubmit } = useForm({
    defaultValues: {
      primary_path: data.primary_path ?? "",
      secondary_path: data.secondary_path ?? "",
      frequency: data.frequency ?? "off",
      enabled: data.enabled ?? false,
    },
  });
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  const onSubmit = async (v) => {
    setMsg(""); setError("");
    try {
      await api.patch("/backups/config/", v);
      setMsg("Saved.");
      onSaved();
    } catch (e) { setError(apiError(e)); }
  };

  return (
    <div className="card space-y-3">
      <h2 className="font-semibold text-gray-900">Destinations &amp; schedule</h2>
      <p className="text-sm text-gray-500">
        Paths must be folders that live outside Docker (bind mounts). Windows-style
        paths are accepted; the secondary (removable drive) is best-effort and
        skipped if not attached.
      </p>
      {error && <ErrorState message={error} />}
      {msg && <p className="text-sm text-green-600">{msg}</p>}
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Primary path (disk)">
            <input className="input" placeholder="D:\SecureBackups" {...register("primary_path")} />
          </Field>
          <Field label="Secondary path (removable drive)">
            <input className="input" placeholder="E:\Backups" {...register("secondary_path")} />
          </Field>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Automatic frequency">
            <select className="input" {...register("frequency")}>
              <option value="off">Off</option>
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
          </Field>
          <label className="flex items-end gap-2 pb-2 text-sm">
            <input type="checkbox" {...register("enabled")} /> Enable scheduled backups
          </label>
        </div>
        <div className="flex justify-end">
          <button className="btn-primary" type="submit">Save</button>
        </div>
      </form>
    </div>
  );
}

function RestoreAudits() {
  const { data } = useFetch("/backups/audits/");
  const calendar = useSettingsStore((s) => s.calendar);
  const dateFormat = useSettingsStore((s) => s.dateFormat);
  const audits = data ?? [];
  if (audits.length === 0) return null;
  return (
    <div className="card">
      <h2 className="mb-3 font-semibold text-gray-900">Restore history</h2>
      <ul className="divide-y divide-gray-100 text-sm">
        {audits.map((a) => (
          <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
            <span className="text-gray-500">{formatDate(a.created_at, calendar, { format: dateFormat, withTime: true })}</span>
            <span className="font-mono text-xs">{a.backup_filename}</span>
            <span className="text-gray-500">by {a.performed_by || "—"}</span>
            <Badge tone={a.status === "success" ? "green" : "red"}>{a.status}</Badge>
          </li>
        ))}
      </ul>
    </div>
  );
}

function RestoreModal({ backup, calendar, dateFormat, onClose, onDone }) {
  const [confirm, setConfirm] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const when = formatDate(backup.timestamp, calendar, { format: dateFormat, withTime: true });
  const ready = confirm.trim().toUpperCase() === "RESTORE" && password.length > 0;

  const submit = async () => {
    setBusy(true); setError("");
    try {
      const { data } = await api.post("/backups/restore/", {
        filename: backup.filename, confirm, password,
      });
      onDone(`Restore complete. Safety backup: ${data.safety_backup}`);
    } catch (e) {
      setError(apiError(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open onClose={onClose} title="Restore backup" wide>
      <div className="space-y-4">
        <div className="flex items-start gap-2 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
          <ShieldAlert size={18} className="mt-0.5 shrink-0" />
          <span>
            Restoring will <b>replace all current data</b> with the state from{" "}
            <b>{when}</b>. Any data created or changed after that time will be lost
            unless it exists in a later backup. A safety backup of the current
            state is taken automatically first.
          </span>
        </div>
        {error && <ErrorState message={error} />}
        <Field label='Type RESTORE to confirm'>
          <input className="input" value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder="RESTORE" />
        </Field>
        <Field label="Re-enter your password">
          <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </Field>
        <div className="flex justify-end gap-2">
          <button className="btn-secondary" onClick={onClose} disabled={busy}>Cancel</button>
          <button className="btn-primary bg-red-600 hover:bg-red-700" disabled={!ready || busy} onClick={submit}>
            {busy ? <RefreshCw size={16} className="animate-spin" /> : <RotateCcw size={16} />} Restore now
          </button>
        </div>
      </div>
    </Modal>
  );
}
