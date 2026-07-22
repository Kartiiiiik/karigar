import { useState } from "react";
import { useForm } from "react-hook-form";
import { DatabaseBackup, Play, ShieldAlert, RefreshCw } from "lucide-react";
import api, { apiError } from "../lib/api";
import { useFetch } from "../hooks/useFetch";
import { PageHeader, Spinner, EmptyState, ErrorState, Field, Badge } from "../components/ui";
import { formatDate } from "../lib/date";
import { useSettingsStore } from "../store/settings";

export default function Backups() {
  const calendar = useSettingsStore((s) => s.calendar);
  const config = useFetch("/backups/config/");
  const logs = useFetch("/backups/logs/", { page_size: 50 });
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false);

  const runNow = async () => {
    setMsg(""); setError(""); setRunning(true);
    try {
      const { data } = await api.post("/backups/run/");
      setMsg(data.detail);
      setTimeout(() => logs.refresh(), 1200);
    } catch (e) {
      setError(apiError(e));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="max-w-3xl space-y-6">
      <PageHeader
        title="Backups"
        subtitle="Export all data as an encrypted archive, emailed to your recipients."
        actions={
          <button className="btn-primary" onClick={runNow} disabled={running}>
            {running ? <RefreshCw size={16} className="animate-spin" /> : <Play size={16} />} Backup now
          </button>
        }
      />

      <div className="flex items-start gap-2 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800">
        <ShieldAlert size={18} className="mt-0.5 shrink-0" />
        <span>
          Backups are AES-encrypted zips; the password is emailed in the message body.
          Email is not a fully secure channel — store the archive and password safely
          and delete the email afterwards.
        </span>
      </div>

      {msg && <p className="text-sm text-green-600">{msg}</p>}
      {error && <ErrorState message={error} />}

      {config.error && <ErrorState message={config.error} />}
      {config.loading ? <Spinner /> : config.data && <ConfigForm data={config.data} onSaved={config.refresh} />}

      <div className="card">
        <h2 className="mb-3 flex items-center gap-2 font-semibold text-gray-900">
          <DatabaseBackup size={18} /> Recent backups
        </h2>
        {logs.loading ? (
          <Spinner />
        ) : (logs.data?.results ?? []).length === 0 ? (
          <EmptyState message="No backups run yet." />
        ) : (
          <ul className="divide-y divide-gray-100 text-sm">
            {logs.data.results.map((l) => (
              <li key={l.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span className="text-gray-500">{formatDate(l.created_at, calendar, { withTime: true })}</span>
                <span className="capitalize text-gray-600">{l.triggered_by}</span>
                <Badge tone={l.status === "success" ? "green" : "red"}>{l.status}</Badge>
                <span className="w-full text-xs text-gray-400 sm:w-auto">{l.message}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function ConfigForm({ data, onSaved }) {
  const { register, handleSubmit } = useForm({
    defaultValues: {
      recipient_emails: data.recipient_emails ?? "",
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
      setMsg("Schedule saved.");
      onSaved();
    } catch (e) {
      setError(apiError(e));
    }
  };

  return (
    <div className="card space-y-3">
      <h2 className="font-semibold text-gray-900">Schedule</h2>
      {error && <ErrorState message={error} />}
      {msg && <p className="text-sm text-green-600">{msg}</p>}
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <Field label="Recipient emails (comma-separated)">
          <input className="input" placeholder="owner@shop.com, backup@shop.com" {...register("recipient_emails")} />
        </Field>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Frequency">
            <select className="input" {...register("frequency")}>
              <option value="off">Off</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
          </Field>
          <label className="flex items-end gap-2 pb-2 text-sm">
            <input type="checkbox" {...register("enabled")} /> Enable scheduled backups
          </label>
        </div>
        <div className="flex justify-end">
          <button className="btn-primary" type="submit">Save schedule</button>
        </div>
      </form>
    </div>
  );
}
