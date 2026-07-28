import { useMemo, useState } from "react";
import { RotateCcw, Trash2 } from "lucide-react";
import api, { apiError } from "../lib/api";
import { useFetch } from "../hooks/useFetch";
import {
  PageHeader, Spinner, EmptyState, ErrorState, Modal, Badge, STICKY_TH,
} from "../components/ui";
import { formatAmount, formatGramsValue } from "../lib/format";
import { formatDate } from "../lib/date";
import { useSettingsStore } from "../store/settings";
import { useAuthStore } from "../store/auth";

const TABS = [
  { key: "gold", label: "Gold", path: "/gold-entries/" },
  { key: "cash", label: "Cash", path: "/cash-entries/" },
];

/**
 * Archived ledger entries — restore them, or (owner only) destroy them for good.
 *
 * Archiving is the app's delete: entries carry balances, so removing one
 * outright would rewrite history with no trace. Everything here is still fully
 * recoverable until an owner deliberately deletes it.
 */
export default function Archive() {
  const [tab, setTab] = useState("gold");
  const isOwner = useAuthStore((s) => s.user?.role) === "owner";

  return (
    <div className="flex h-full flex-col">
      <div className="hidden sm:block">
        <PageHeader
          title="Archive"
          subtitle="Entries removed from the ledgers. They count towards no balance until restored."
        />
      </div>

      <div className="mb-3 flex shrink-0 gap-2 border-b border-gray-200">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
              tab === t.key
                ? "border-brand-600 text-brand-700"
                : "border-transparent text-gray-500"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex min-h-0 flex-1 flex-col">
        <ArchivedList
          key={tab}
          kind={tab}
          path={TABS.find((t) => t.key === tab).path}
          isOwner={isOwner}
        />
      </div>
    </div>
  );
}

function ArchivedList({ kind, path, isOwner }) {
  const calendar = useSettingsStore((s) => s.calendar);
  const dateFormat = useSettingsStore((s) => s.dateFormat);
  const [search, setSearch] = useState("");
  const params = useMemo(
    () => ({ archived: true, page_size: 500, ...(search ? { search } : {}) }),
    [search],
  );
  const { data, loading, error, refresh } = useFetch(path, params);
  const [confirming, setConfirming] = useState(null);
  const items = data?.results ?? [];

  const isGold = kind === "gold";
  const td = "border-b border-gray-100 px-3 py-2.5 align-top";
  const date = (v) => formatDate(v, calendar, { format: dateFormat });

  return (
    <div className="flex h-full flex-col">
      <div className="mb-3 flex shrink-0 flex-wrap items-center gap-2">
        <p className="text-sm text-gray-500">
          {items.length} archived {isGold ? "gold" : "cash"}{" "}
          {items.length === 1 ? "entry" : "entries"}
        </p>
        <input
          className="input sm:ml-auto sm:w-64"
          placeholder="Search amount, order, remarks…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {error && <ErrorState message={error} />}

      {loading && !data ? (
        <Spinner />
      ) : items.length === 0 ? (
        <EmptyState
          message={
            search
              ? "No archived entries match that search."
              : "Nothing archived. Entries you archive from the ledger appear here."
          }
        />
      ) : (
        <div className="min-h-0 flex-1 overflow-auto rounded-xl border border-gray-200 bg-white">
          <table className="min-w-full border-separate border-spacing-0 text-sm">
            <thead className="text-left text-xs uppercase text-gray-500">
              <tr>
                <th className={STICKY_TH}>Entry date</th>
                <th className={STICKY_TH}>Karigar</th>
                <th className={STICKY_TH}>{isGold ? "Net" : "Amount"}</th>
                <th className={STICKY_TH}>Order</th>
                <th className={STICKY_TH}>Archived</th>
                <th className={STICKY_TH}>Reason</th>
                <th className={STICKY_TH}></th>
              </tr>
            </thead>
            <tbody>
              {items.map((e) => (
                <tr key={e.id} className="hover:bg-gray-50">
                  <td className={`${td} whitespace-nowrap text-gray-600`}>{date(e.entry_date)}</td>
                  <td className={`${td} whitespace-nowrap`}>{e.karigar_name}</td>
                  <td className={`${td} whitespace-nowrap`}>
                    <Badge tone={e.direction === "dr" ? "amber" : "green"}>
                      {e.direction === "dr" ? "Dr" : "Cr"}
                    </Badge>{" "}
                    <span className="font-medium">
                      {isGold
                        ? `${formatGramsValue(e.net_weight_g)} g`
                        : formatAmount(e.amount_npr)}
                    </span>
                    {isGold && <span className="text-gray-400"> · {e.carat}kt</span>}
                  </td>
                  <td className={`${td} whitespace-nowrap text-gray-600`}>
                    {e.order ? `#${e.order}` : "—"}
                  </td>
                  <td className={`${td} whitespace-nowrap text-gray-600`}>
                    {date(e.archived_at)}
                    <span className="block text-xs text-gray-400">{e.archived_by || "—"}</span>
                  </td>
                  <td className={`${td} text-gray-500`}>{e.archive_reason || "—"}</td>
                  <td className={`${td} whitespace-nowrap text-right`}>
                    <div className="flex justify-end gap-1">
                      <button
                        className="p-1 text-gray-400 hover:text-brand-600"
                        title="Restore to the ledger"
                        onClick={() => setConfirming({ kind: "restore", entry: e })}
                      >
                        <RotateCcw size={15} />
                      </button>
                      {isOwner && (
                        <button
                          className="p-1 text-gray-400 hover:text-danger"
                          title="Delete permanently"
                          onClick={() => setConfirming({ kind: "delete", entry: e })}
                        >
                          <Trash2 size={15} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!isOwner && items.length > 0 && (
        <p className="shrink-0 pt-2 text-xs text-gray-400">
          Only the shop owner can delete an archived entry permanently.
        </p>
      )}

      {confirming && (
        <ConfirmAction
          {...confirming}
          path={path}
          isGold={isGold}
          onClose={() => setConfirming(null)}
          onDone={() => { setConfirming(null); refresh(); }}
        />
      )}
    </div>
  );
}

function ConfirmAction({ kind, entry, path, isGold, onClose, onDone }) {
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const restoring = kind === "restore";

  const label = isGold
    ? `${entry.direction === "dr" ? "Dr" : "Cr"} ${formatGramsValue(entry.net_weight_g)} g`
    : `${entry.direction === "dr" ? "Dr" : "Cr"} ${formatAmount(entry.amount_npr)}`;

  const run = async () => {
    setError("");
    setSaving(true);
    try {
      if (restoring) await api.post(`${path}${entry.id}/restore/`);
      else await api.delete(`${path}${entry.id}/`);
      onDone();
    } catch (e) {
      setError(apiError(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open
      onClose={onClose}
      title={restoring ? "Restore this entry?" : "Delete permanently?"}
    >
      <div className="space-y-4">
        {error && <ErrorState message={error} />}

        <div className="rounded-lg bg-gray-50 px-3 py-2 text-sm">
          <p className="font-medium">{label}</p>
          <p className="text-xs text-gray-500">
            {entry.karigar_name}
            {entry.archive_reason ? ` · ${entry.archive_reason}` : ""}
          </p>
        </div>

        <p className="text-sm text-gray-600">
          {restoring ? (
            <>
              It goes back into the ledger and counts towards {entry.karigar_name}&rsquo;s balance
              again{entry.order ? ` and towards order #${entry.order}` : ""}.
            </>
          ) : (
            <>
              This cannot be undone. The entry and its history are removed from the database for
              good. If you might need it again, leave it archived — an archived entry already
              counts towards nothing.
            </>
          )}
        </p>

        <div className="flex justify-end gap-2">
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button
            className={restoring ? "btn-primary" : "btn-danger"}
            disabled={saving}
            onClick={run}
          >
            {restoring ? <RotateCcw size={16} /> : <Trash2 size={16} />}
            {saving ? "Working…" : restoring ? "Restore" : "Delete for good"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
