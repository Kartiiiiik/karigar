import { useEffect, useState } from "react";
import { Archive } from "lucide-react";
import api, { apiError } from "../lib/api";
import { Modal, Field, ErrorState, Spinner } from "./ui";

/**
 * Confirm archiving a gold or cash entry.
 *
 * Before asking, it fetches `/…/archive-impact/`, which the server computes by
 * actually performing the archive inside a savepoint and rolling it back. What
 * this dialog promises is therefore what will happen — there is no second copy
 * of the rules here that could drift from the real thing.
 */
export default function ArchiveDialog({ kind, entry, onClose, onDone }) {
  const base = kind === "gold" ? "gold-entries" : "cash-entries";
  const unit = kind === "gold" ? " g" : "";
  const [impact, setImpact] = useState(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .get(`/${base}/${entry.id}/archive-impact/`)
      .then(({ data }) => !cancelled && setImpact(data))
      .catch((e) => !cancelled && setError(apiError(e)));
    return () => {
      cancelled = true;
    };
  }, [base, entry.id]);

  const confirm = async () => {
    setError("");
    setSaving(true);
    try {
      await api.post(`/${base}/${entry.id}/archive/`, { reason });
      onDone();
    } catch (e) {
      setError(apiError(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open onClose={onClose} title="Archive this entry?">
      <div className="space-y-4">
        {error && <ErrorState message={error} />}

        {!impact && !error ? (
          <Spinner label="Working out the impact…" />
        ) : impact ? (
          <div className="space-y-2 rounded-lg border border-gray-200 p-3 text-sm">
            <Row label="Entry" value={impact.entry_label} />
            <Row
              label={`${impact.karigar_name}'s balance`}
              value={<Change before={`${impact.balance_before}${unit}`} after={`${impact.balance_after}${unit}`} />}
            />
          </div>
        ) : null}

        <Field label="Reason (optional)">
          <input
            className="input"
            placeholder="e.g. keyed twice, wrong karigar"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </Field>

        <div className="flex justify-end gap-2">
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-danger" disabled={saving || !impact} onClick={confirm}>
            <Archive size={16} /> {saving ? "Archiving…" : "Archive entry"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex flex-wrap justify-between gap-2">
      <span className="text-gray-500">{label}</span>
      <span className="text-right">{value}</span>
    </div>
  );
}

function Change({ before, after }) {
  if (before === after) return <span>{after}</span>;
  return (
    <>
      <span className="text-gray-400 line-through">{before}</span>
      {" → "}
      <span className="font-semibold">{after}</span>
    </>
  );
}
