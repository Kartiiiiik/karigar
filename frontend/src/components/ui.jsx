import { X, Loader2, Inbox, AlertCircle, ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";

export function PageHeader({ title, subtitle, actions }) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
        {subtitle && <p className="text-sm text-gray-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </div>
  );
}

export function Spinner({ label = "Loading…" }) {
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-gray-500">
      <Loader2 className="animate-spin" size={20} /> {label}
    </div>
  );
}

export function EmptyState({ message = "Nothing here yet." }) {
  return (
    <div className="flex flex-col items-center gap-2 py-12 text-gray-400">
      <Inbox size={28} />
      <p className="text-sm">{message}</p>
    </div>
  );
}

export function ErrorState({ message }) {
  return (
    <div className="flex items-center gap-2 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
      <AlertCircle size={18} /> {message}
    </div>
  );
}

export function Badge({ children, tone = "gray" }) {
  const tones = {
    gray: "bg-gray-100 text-gray-700",
    green: "bg-green-100 text-green-700",
    red: "bg-red-100 text-red-700",
    amber: "bg-amber-100 text-amber-700",
    blue: "bg-blue-100 text-blue-700",
  };
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
}

/** Dr/Cr tinted badge from a signed value. */
export function DrCrBadge({ label }) {
  if (!label || label === "Settled") return <Badge tone="gray">Settled</Badge>;
  const tone = label.endsWith("Dr") ? "amber" : "green";
  return <Badge tone={tone}>{label}</Badge>;
}

export function Modal({ open, onClose, title, children, wide }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-4">
      <div
        className={`w-full ${wide ? "sm:max-w-2xl" : "sm:max-w-md"} max-h-[90vh] overflow-y-auto rounded-t-2xl bg-white p-5 shadow-xl sm:rounded-2xl`}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="text-gray-400 hover:text-gray-600">
            <X size={20} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

// Shared sticky-header cell classes for the scrollable ledger tables.
export const STICKY_TH = "sticky top-0 z-20 h-10 border-b border-gray-200 bg-gray-50 px-3 py-2 text-left";

/** Clickable, sticky table header that toggles asc/desc for `field`. */
export function SortableTh({ label, field, ordering, onSort }) {
  const asc = ordering === field;
  const desc = ordering === `-${field}`;
  return (
    <th className={`${STICKY_TH} cursor-pointer select-none hover:text-gray-700`} onClick={() => onSort(field)}>
      <span className="inline-flex items-center gap-1">
        {label}
        {asc ? <ChevronUp size={12} /> : desc ? <ChevronDown size={12} /> : <ChevronsUpDown size={12} className="opacity-30" />}
      </span>
    </th>
  );
}

export function Field({ label, error, children, required }) {
  return (
    <div>
      <label className="label">
        {label} {required && <span className="text-red-500">*</span>}
      </label>
      {children}
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  );
}
