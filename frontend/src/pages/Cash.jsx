import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useForm, useWatch } from "react-hook-form";
import DateInput from "../components/DateInput";
import Select, { FormSelect } from "../components/Select";
import { ArrowUpRight, ArrowDownLeft, Pencil, Archive } from "lucide-react";
import ArchiveDialog from "../components/ArchiveDialog";
import api, { apiError } from "../lib/api";
import { useFetch } from "../hooks/useFetch";
import { PageHeader, Spinner, EmptyState, ErrorState, Modal, Field, SortableTh, STICKY_TH } from "../components/ui";
import { formatAmount } from "../lib/format";

// Unit label for column headers (keeps rows unit-free).
const NPR = <sub className="ml-0.5 text-[10px] font-normal text-gray-400">npr</sub>;
import { formatDate } from "../lib/date";
import { useSettingsStore } from "../store/settings";
import { useAuthStore } from "../store/auth";

export default function Cash() {
  const calendar = useSettingsStore((s) => s.calendar);
  const dateFormat = useSettingsStore((s) => s.dateFormat);
  const role = useAuthStore((s) => s.user?.role);
  const isStaff = role === "owner" || role === "manager";
  const [filters, setFilters] = useState({ karigar: "", direction: "", search: "" });
  const [ordering, setOrdering] = useState("-entry_date");

  const clean = Object.fromEntries(Object.entries(filters).filter(([, v]) => v));
  const cleanKey = JSON.stringify(clean);
  const listParams = useMemo(
    () => ({ page_size: 1000, ordering, ...clean }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [ordering, cleanKey],
  );
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const summaryParams = useMemo(() => clean, [cleanKey]);
  const { data, loading, error, refresh } = useFetch("/cash-entries/", listParams);
  const summary = useFetch("/cash-entries/summary/", summaryParams);
  const { data: karigarData, refresh: refreshKarigars } = useFetch(
    "/karigars/", isStaff ? { page_size: 200 } : null,
  );
  const [entry, setEntry] = useState(null);
  const [archiving, setArchiving] = useState(null);
  const karigars = karigarData?.results ?? [];
  const items = data?.results ?? [];
  const count = data?.count ?? 0;

  // Open the give/receive form when arrived via a dashboard quick action.
  const [sp, setSp] = useSearchParams();
  useEffect(() => {
    if (!isStaff) return;
    const a = sp.get("action");
    if (a === "out") setEntry({ direction: "dr" });
    else if (a === "in") setEntry({ direction: "cr" });
    if (a) {
      sp.delete("action");
      setSp(sp, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Any write moves the rows, the Total row AND the karigar's running
  // balance behind the Opening/Closing rows — reload all three together.
  const reload = () => { refresh(); summary.refresh(); refreshKarigars(); };

  const sort = (field) => setOrdering((o) => (o === field ? `-${field}` : field));

  const selected = filters.karigar
    ? karigars.find((k) => String(k.id) === String(filters.karigar))
    : null;
  const searchDisabled = isStaff && !filters.karigar;
  const openingSigned = selected ? Number(selected.opening_cash_npr) : 0;
  const openingInDr = openingSigned >= 0;
  const openingAbs = Math.abs(openingSigned);
  const sumDr = Number(summary.data?.total_dr ?? 0);
  const sumCr = Number(summary.data?.total_cr ?? 0);
  const totalDebit = sumDr + (selected && openingInDr ? openingAbs : 0);
  const totalCredit = sumCr + (selected && !openingInDr ? openingAbs : 0);
  const cashClosing = selected ? Number(selected.cash_balance) : sumDr - sumCr;

  // Sticky-cell classes + summary rows (cols: Date, Karigar, Debit, Credit, Order, Remarks, [action]).
  const openTd = "sticky top-10 z-10 h-10 whitespace-nowrap border-b border-amber-200 bg-amber-50 px-3 font-semibold text-gray-800";
  const bodyTd = "whitespace-nowrap border-b border-gray-100 px-3 py-2.5";
  const footTd = "sticky z-20 h-10 whitespace-nowrap border-t border-amber-200 bg-amber-50 px-3 font-semibold text-gray-800";
  const totalBottom = selected ? "bottom-10" : "bottom-0";
  const act = isStaff ? [""] : [];
  const openingCells = ["Opening", selected?.full_name ?? "",
    openingInDr ? formatAmount(openingAbs) : "", !openingInDr ? formatAmount(openingAbs) : "", "", "", ...act];
  const totalCells = [`Total (${summary.data?.count ?? count})`, "",
    formatAmount(totalDebit), formatAmount(totalCredit), "", "", ...act];
  const closingCells = [`Closing (${cashClosing >= 0 ? "Dr" : "Cr"})`, "",
    cashClosing >= 0 ? formatAmount(cashClosing) : "", cashClosing < 0 ? formatAmount(-cashClosing) : "", "", "", ...act];

  return (
    <div className="flex h-full flex-col">
      <div className="hidden sm:block">
        <PageHeader title="Cash Ledger" subtitle="NPR advances & payments. Dr = given to karigar, Cr = received." />
      </div>

      <div className="mb-3 shrink-0 space-y-2">
        {isStaff && (
          <div className="flex gap-2">
            <button className="btn-primary flex-1 sm:flex-none" onClick={() => setEntry({ direction: "dr" })}>
              <ArrowUpRight size={16} /> Give cash
            </button>
            <button className="btn-secondary flex-1 sm:flex-none" onClick={() => setEntry({ direction: "cr" })}>
              <ArrowDownLeft size={16} /> Receive cash
            </button>
          </div>
        )}
        <div className="flex flex-wrap gap-2 sm:justify-end">
          {isStaff && (
            <Select
              className="min-w-0 flex-1 sm:w-40 sm:flex-none"
              aria-label="Filter by karigar"
              value={filters.karigar}
              onChange={(v) =>
                setFilters((f) => ({ ...f, karigar: v, search: v ? f.search : "" }))
              }
              options={[
                { value: "", label: "All karigars" },
                ...karigars.map((k) => ({ value: k.id, label: k.full_name })),
              ]}
            />
          )}
          <Select
            className="w-24 shrink-0 sm:w-36"
            aria-label="Filter by direction"
            value={filters.direction}
            onChange={(v) => setFilters((f) => ({ ...f, direction: v }))}
            options={[
              { value: "", label: "Dr & Cr" },
              { value: "dr", label: "Dr" },
              { value: "cr", label: "Cr" },
            ]}
          />
          <input
            className="input w-full sm:w-56"
            placeholder={searchDisabled ? "Select a karigar to search" : "Search amount, remarks, order…"}
            value={filters.search}
            disabled={searchDisabled}
            onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value }))}
          />
        </div>
      </div>

      {error && <ErrorState message={error} />}
      {loading && !data ? (
        <Spinner />
      ) : count === 0 ? (
        <EmptyState message="No cash entries." />
      ) : (
        <div className="min-h-0 flex-1 overflow-auto rounded-xl border border-gray-200 bg-white">
          <table className="min-w-full border-separate border-spacing-0 text-sm">
            <thead className="text-left text-xs uppercase text-gray-500">
              <tr>
                <SortableTh label="Date" field="entry_date" ordering={ordering} onSort={sort} />
                <th className={STICKY_TH}>Karigar</th>
                <SortableTh label={<>Debit{NPR}</>} field="amount_npr" ordering={ordering} onSort={sort} />
                <SortableTh label={<>Credit{NPR}</>} field="amount_npr" ordering={ordering} onSort={sort} />
                <th className={STICKY_TH}>Order</th>
                <th className={STICKY_TH}>Remarks</th>
                {isStaff && <th className={STICKY_TH}></th>}
              </tr>
            </thead>
            <tbody>
              {selected && (
                <tr>{openingCells.map((c, i) => <td key={i} className={openTd}>{c}</td>)}</tr>
              )}
              {items.map((e) => (
                <tr key={e.id} className="hover:bg-gray-50">
                  <td className={`${bodyTd} whitespace-nowrap text-gray-600`}>{formatDate(e.entry_date, calendar, { format: dateFormat })}</td>
                  <td className={bodyTd}>{e.karigar_name}</td>
                  <td className={`${bodyTd} font-medium text-dr`}>{e.direction === "dr" ? formatAmount(e.amount_npr) : ""}</td>
                  <td className={`${bodyTd} font-medium text-cr`}>{e.direction === "cr" ? formatAmount(e.amount_npr) : ""}</td>
                  <td className={`${bodyTd} text-gray-600`}>{e.order_number || "—"}</td>
                  <td className={`${bodyTd} text-gray-500`}>{e.remarks || "—"}</td>
                  {isStaff && (
                    <td className={`${bodyTd} text-right`}>
                      <div className="flex justify-end gap-1">
                      <button className="p-1 text-gray-400 hover:text-brand-600" title="Edit entry" onClick={() => setEntry(e)}>
                        <Pencil size={15} />
                      </button>
                      <button className="p-1 text-gray-400 hover:text-danger" title="Archive entry" onClick={() => setArchiving(e)}>
                        <Archive size={15} />
                      </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>{totalCells.map((c, i) => <td key={i} className={`${footTd} ${totalBottom}`}>{c}</td>)}</tr>
              {selected && (
                <tr>{closingCells.map((c, i) => <td key={i} className={`${footTd} bottom-0`}>{c}</td>)}</tr>
              )}
            </tfoot>
          </table>
        </div>
      )}

      {archiving && (
        <ArchiveDialog
          kind="cash"
          entry={archiving}
          onClose={() => setArchiving(null)}
          onDone={() => { setArchiving(null); reload(); }}
        />
      )}

      {entry && (
        <CashEntryForm
          entry={entry}
          karigars={karigars}
          onClose={() => setEntry(null)}
          onSaved={() => { setEntry(null); reload(); }}
        />
      )}
    </div>
  );
}

function CashEntryForm({ entry, karigars, onClose, onSaved }) {
  const isEdit = Boolean(entry.id);
  const direction = entry.direction;
  const calendar = useSettingsStore((s) => s.calendar);
  const { register, handleSubmit, control, setValue } = useForm({
    defaultValues: {
      // Select values are strings, matching what the native select reported.
      karigar: entry.karigar != null ? String(entry.karigar) : "",
      amount_npr: entry.amount_npr ?? "",
      order_number: entry.order_number ?? "",
      remarks: entry.remarks ?? "",
      entry_date: entry.entry_date ?? new Date().toISOString().slice(0, 10),
    },
  });
  const entryDate = useWatch({ control, name: "entry_date" });
  const [error, setError] = useState("");

  const onSubmit = async (v) => {
    setError("");
    const payload = {
      karigar: v.karigar,
      direction,
      amount_npr: v.amount_npr,
      order_number: v.order_number || "",
      remarks: v.remarks || "",
      entry_date: v.entry_date,
    };
    try {
      if (isEdit) await api.patch(`/cash-entries/${entry.id}/`, payload);
      else await api.post("/cash-entries/", payload);
      onSaved();
    } catch (e) {
      setError(apiError(e));
    }
  };

  const title = isEdit ? "Edit cash entry" : direction === "dr" ? "Give cash (Dr)" : "Receive cash (Cr)";

  return (
    <Modal open onClose={onClose} title={title}>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {error && <ErrorState message={error} />}
        <Field label="Karigar" required>
          <FormSelect
            control={control}
            name="karigar"
            rules={{ required: true }}
            disabled={isEdit}
            placeholder="Select karigar…"
            options={karigars.map((k) => ({ value: k.id, label: k.full_name }))}
          />
        </Field>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Amount (NPR)" required>
            <input className="input" type="number" step="0.01" min="0.01" {...register("amount_npr", { required: true })} />
          </Field>
          <Field label={`Date (${calendar})`} required>
            <DateInput calendar={calendar} value={entryDate}
              onChange={(v) => setValue("entry_date", v)} />
          </Field>
        </div>
        {/* Just the number written on the paperwork — a label on this entry,
            not a link to anything. */}
        <Field label="Order number (optional)">
          <input className="input" placeholder="e.g. ORD-1002" {...register("order_number")} />
        </Field>

        <Field label="Remarks">
          <textarea className="input" rows={2} {...register("remarks")} />
        </Field>
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary">Save</button>
        </div>
      </form>
    </Modal>
  );
}
