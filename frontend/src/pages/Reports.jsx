import { useState } from "react";
import { FileSpreadsheet, FileText, Eye } from "lucide-react";
import api, { apiError } from "../lib/api";
import { useFetch } from "../hooks/useFetch";
import { PageHeader, Spinner, ErrorState, Field, STICKY_TH } from "../components/ui";
import { formatDate, BS_MONTHS, monthRangeToApi, currentYear } from "../lib/date";
import { useSettingsStore } from "../store/settings";

const AD_MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

// Sticky amber cells for the pinned opening row and total/closing footer.
const openTd = "sticky top-10 z-10 h-10 whitespace-nowrap border-b border-amber-200 bg-amber-50 px-3 font-semibold text-gray-800";
const footTd = "sticky z-20 h-10 whitespace-nowrap border-t border-amber-200 bg-amber-50 px-3 font-semibold text-gray-800";

export default function Reports() {
  const calendar = useSettingsStore((s) => s.calendar);
  const { data: karigarData } = useFetch("/karigars/", { page_size: 200 });
  const karigars = karigarData?.results ?? [];

  const [kind, setKind] = useState("gold");
  // period: month (0-based index as string) + year; when both set, month mode is
  // active and the free date range is disabled.
  const [form, setForm] = useState({ date_from: "", date_to: "", karigar: "", month: "", year: "" });
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const months = calendar === "BS" ? BS_MONTHS : AD_MONTHS;
  const baseYear = currentYear(calendar);
  const years = Array.from({ length: 8 }, (_, i) => baseYear - 6 + i);
  const monthMode = form.month !== "" && form.year !== "";

  const query = () => {
    const p = {};
    if (form.karigar) p.karigar = form.karigar;
    if (monthMode) {
      const { from, to } = monthRangeToApi(calendar, Number(form.year), Number(form.month));
      p.date_from = from;
      p.date_to = to;
    } else {
      if (form.date_from) p.date_from = form.date_from;
      if (form.date_to) p.date_to = form.date_to;
    }
    return p;
  };

  const preview = async () => {
    setLoading(true);
    setError("");
    setReport(null);
    try {
      const { data } = await api.get(`/reports/${kind}/`, { params: query() });
      setReport(data);
    } catch (e) {
      setError(apiError(e));
    } finally {
      setLoading(false);
    }
  };

  const download = async (fmt) => {
    setError("");
    try {
      const params = { ...query(), fmt };
      const resp = await api.get(`/reports/${kind}/`, { params, responseType: "blob" });
      const url = URL.createObjectURL(resp.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${kind}-report.${fmt === "excel" ? "xlsx" : "pdf"}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(apiError(e, "Export failed."));
    }
  };

  return (
    <div>
      <PageHeader title="Reports" subtitle="Cash and gold ledgers by date range or month, with Excel & PDF export." />

      <div className="card mb-6 space-y-4">
        <div className="flex gap-2">
          {["gold", "cash"].map((k) => (
            <button
              key={k}
              onClick={() => { setKind(k); setReport(null); }}
              className={`rounded-lg px-4 py-2 text-sm font-medium capitalize ${
                kind === k ? "bg-brand-600 text-white" : "border border-gray-300 text-gray-600"
              }`}
            >
              {k} report
            </button>
          ))}
        </div>

        {/* Month / year quick period. Selecting a month disables the date range. */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Field label={`Month (${calendar})`}>
            <select className="input" value={form.month}
              onChange={(e) => setForm((f) => ({ ...f, month: e.target.value }))}>
              <option value="">— Custom range —</option>
              {months.map((m, i) => <option key={m} value={i}>{m}</option>)}
            </select>
          </Field>
          <Field label={`Year (${calendar})`}>
            <select className="input" value={form.year}
              onChange={(e) => setForm((f) => ({ ...f, year: e.target.value }))}>
              <option value="">—</option>
              {years.map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
          </Field>
          <Field label="Karigar">
            <select className="input" value={form.karigar}
              onChange={(e) => setForm((f) => ({ ...f, karigar: e.target.value }))}>
              <option value="">All karigars</option>
              {karigars.map((k) => <option key={k.id} value={k.id}>{k.full_name}</option>)}
            </select>
          </Field>
        </div>

        {/* Free date range — disabled while a month is selected. */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Field label="From (AD)">
            <input className="input" type="date" value={form.date_from} disabled={monthMode}
              onChange={(e) => setForm((f) => ({ ...f, date_from: e.target.value }))} />
            {calendar === "BS" && form.date_from && !monthMode && (
              <p className="mt-1 text-xs text-gray-400">{formatDate(form.date_from, "BS")}</p>
            )}
          </Field>
          <Field label="To (AD)">
            <input className="input" type="date" value={form.date_to} disabled={monthMode}
              onChange={(e) => setForm((f) => ({ ...f, date_to: e.target.value }))} />
            {calendar === "BS" && form.date_to && !monthMode && (
              <p className="mt-1 text-xs text-gray-400">{formatDate(form.date_to, "BS")}</p>
            )}
          </Field>
          <div className="flex items-end">
            <button className="btn-primary w-full" onClick={preview}>
              <Eye size={16} /> Preview
            </button>
          </div>
        </div>

        {monthMode && (
          <p className="text-xs text-gray-400">
            Showing {months[Number(form.month)]} {form.year} — the date range is disabled.
          </p>
        )}

        <div className="flex flex-wrap gap-2">
          <button className="btn-secondary" onClick={() => download("excel")}>
            <FileSpreadsheet size={16} /> Export Excel
          </button>
          <button className="btn-secondary" onClick={() => download("pdf")}>
            <FileText size={16} /> Export PDF
          </button>
        </div>
      </div>

      {error && <ErrorState message={error} />}
      {loading && <Spinner label="Building report…" />}

      {report && (
        <div className="space-y-3">
          <div>
            <h2 className="font-semibold text-gray-900">{report.title}</h2>
            <p className="text-sm text-gray-500">{report.subtitle}</p>
          </div>
          <div className="max-h-[calc(100dvh_-_20rem)] min-h-[240px] overflow-auto rounded-xl border border-gray-200 bg-white">
            <table className="min-w-full border-separate border-spacing-0 text-sm">
              <thead className="text-left text-xs uppercase text-gray-500">
                <tr>{report.columns.map((c) => <th key={c} className={STICKY_TH}>{c}</th>)}</tr>
              </thead>
              <tbody>
                {report.opening_row && (
                  <tr>
                    {report.opening_row.map((cell, j) => <td key={j} className={openTd}>{cell}</td>)}
                  </tr>
                )}
                {report.rows.length === 0 ? (
                  <tr>
                    <td className="border-b border-gray-100 px-3 py-6 text-center text-gray-400" colSpan={report.columns.length}>
                      No entries in this range.
                    </td>
                  </tr>
                ) : (
                  report.rows.map((row, i) => (
                    <tr key={i} className="hover:bg-gray-50">
                      {row.map((cell, j) => <td key={j} className="whitespace-nowrap border-b border-gray-100 px-3 py-2">{cell}</td>)}
                    </tr>
                  ))
                )}
              </tbody>
              <tfoot>
                {report.total_row && (
                  <tr>
                    {report.total_row.map((cell, j) => (
                      <td key={j} className={`${footTd} ${report.closing_row ? "bottom-10" : "bottom-0"}`}>{cell}</td>
                    ))}
                  </tr>
                )}
                {report.closing_row && (
                  <tr>
                    {report.closing_row.map((cell, j) => <td key={j} className={`${footTd} bottom-0`}>{cell}</td>)}
                  </tr>
                )}
              </tfoot>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
