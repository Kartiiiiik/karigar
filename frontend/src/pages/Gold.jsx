import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useForm, useWatch } from "react-hook-form";
import { Plus, ArrowUpRight, ArrowDownLeft, Pencil, Archive } from "lucide-react";
import ArchiveDialog from "../components/ArchiveDialog";
import api, { apiError } from "../lib/api";
import { useFetch } from "../hooks/useFetch";
import {
  PageHeader, Spinner, EmptyState, ErrorState, Modal, Field, SortableTh, STICKY_TH,
} from "../components/ui";
import DateInput from "../components/DateInput";
import { formatGramsValue } from "../lib/format";

// Small unit label shown in a column header (keeps rows unit-free).
const GMS = <sub className="ml-0.5 text-[10px] font-normal text-gray-400">gms</sub>;
import { formatDate } from "../lib/date";
import { useSettingsStore } from "../store/settings";
import { useAuthStore } from "../store/auth";

// Live net-weight preview mirrors the backend: net = gross * carat/24.
function netPreview(gross, carat) {
  const g = Number(gross || 0);
  const c = Number(carat || 24);
  return (g * (c / 24)).toFixed(3);
}

export default function Gold() {
  const role = useAuthStore((s) => s.user?.role);
  const isStaff = role === "owner" || role === "manager";

  return (
    <div className="flex h-full flex-col">
      <div className="hidden sm:block">
        <PageHeader title="Gold Ledger" subtitle="Balances are net weight (grams). Dr = given, Cr = received." />
      </div>
      <div className="flex min-h-0 flex-1 flex-col">
        <Entries isStaff={isStaff} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Entries
// ---------------------------------------------------------------------------
function Entries({ isStaff }) {
  const calendar = useSettingsStore((s) => s.calendar);
  const dateFormat = useSettingsStore((s) => s.dateFormat);
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
  const { data, loading, error, refresh } = useFetch("/gold-entries/", listParams);
  const summary = useFetch("/gold-entries/summary/", summaryParams);
  const { data: karigarData, refresh: refreshKarigars } = useFetch(
    "/karigars/", isStaff ? { page_size: 200 } : null,
  );
  const [entry, setEntry] = useState(null);
  const [archiving, setArchiving] = useState(null);
  const karigars = karigarData?.results ?? [];
  const items = data?.results ?? [];
  const count = data?.count ?? 0;

  // Open the issue/receive form when arrived via a dashboard quick action.
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

  // Opening/closing come from the karigar (full ledger); the Total row uses the
  // server-side summary so it stays correct regardless of what's scrolled.
  const selected = filters.karigar
    ? karigars.find((k) => String(k.id) === String(filters.karigar))
    : null;
  const searchDisabled = isStaff && !filters.karigar;
  const openingSigned = selected ? Number(selected.opening_gold_g) : 0;
  const openingInDr = openingSigned >= 0;
  const openingAbs = Math.abs(openingSigned);
  const sumDr = Number(summary.data?.total_dr ?? 0);
  const sumCr = Number(summary.data?.total_cr ?? 0);
  const totalNetDr = sumDr + (selected && openingInDr ? openingAbs : 0);
  const totalNetCr = sumCr + (selected && !openingInDr ? openingAbs : 0);
  const goldClosing = selected ? Number(selected.gold_balance) : sumDr - sumCr;

  // Sticky-cell class strings + summary-row cell arrays (aligned to columns:
  // Date, Karigar, Gross, Carat, Net Dr, Net Cr, Ornament, Order, [action]).
  const openTd = "sticky top-10 z-10 h-10 whitespace-nowrap border-b border-amber-200 bg-amber-50 px-3 font-semibold text-gray-800";
  const bodyTd = "whitespace-nowrap border-b border-gray-100 px-3 py-2.5";
  const footTd = "sticky z-20 h-10 whitespace-nowrap border-t border-amber-200 bg-amber-50 px-3 font-semibold text-gray-800";
  const totalBottom = selected ? "bottom-10" : "bottom-0";
  const act = isStaff ? [""] : [];
  const openingCells = ["Opening", selected?.full_name ?? "", "", "",
    openingInDr ? formatGramsValue(openingAbs) : "", !openingInDr ? formatGramsValue(openingAbs) : "", "", "", ...act];
  const totalCells = [`Total (${summary.data?.count ?? count})`, "", "", "",
    formatGramsValue(totalNetDr), formatGramsValue(totalNetCr), "", "", ...act];
  const closingCells = [`Closing (${goldClosing >= 0 ? "Dr" : "Cr"})`, "", "", "",
    goldClosing >= 0 ? formatGramsValue(goldClosing) : "", goldClosing < 0 ? formatGramsValue(-goldClosing) : "", "", "", ...act];

  return (
    <div className="flex h-full flex-col">
      <div className="mb-4 shrink-0 space-y-2">
        {isStaff && (
          <div className="flex gap-2">
            <button className="btn-primary flex-1 sm:flex-none" onClick={() => setEntry({ direction: "dr" })}>
              <ArrowUpRight size={16} /> Issue gold
            </button>
            <button className="btn-secondary flex-1 sm:flex-none" onClick={() => setEntry({ direction: "cr" })}>
              <ArrowDownLeft size={16} /> Receive
            </button>
          </div>
        )}
        <div className="flex flex-wrap gap-2 sm:justify-end">
          {isStaff && (
            <select
              className="input min-w-0 flex-1 truncate sm:w-40 sm:flex-none"
              value={filters.karigar}
              onChange={(e) =>
                setFilters((f) => ({ ...f, karigar: e.target.value, search: e.target.value ? f.search : "" }))
              }
            >
              <option value="">All karigars</option>
              {karigars.map((k) => <option key={k.id} value={k.id}>{k.full_name}</option>)}
            </select>
          )}
          <select
            className="input w-24 shrink-0 sm:w-36"
            value={filters.direction}
            onChange={(e) => setFilters((f) => ({ ...f, direction: e.target.value }))}
          >
            <option value="">Dr &amp; Cr</option>
            <option value="dr">Dr</option>
            <option value="cr">Cr</option>
          </select>
          <input
            className="input w-full sm:w-56"
            placeholder={searchDisabled ? "Select a karigar to search" : "Search amount, ornament, order…"}
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
        <EmptyState message="No gold entries." />
      ) : (
        <div className="min-h-0 flex-1 overflow-auto rounded-xl border border-gray-200 bg-white">
          <table className="min-w-full border-separate border-spacing-0 text-sm">
            <thead className="text-left text-xs uppercase text-gray-500">
              <tr>
                <SortableTh label="Date" field="entry_date" ordering={ordering} onSort={sort} />
                <th className={STICKY_TH}>Karigar</th>
                <SortableTh label={<>Gross{GMS}</>} field="gross_weight_g" ordering={ordering} onSort={sort} />
                <SortableTh label="Carat" field="carat" ordering={ordering} onSort={sort} />
                <SortableTh label={<>Net Dr{GMS}</>} field="net_weight_g" ordering={ordering} onSort={sort} />
                <SortableTh label={<>Net Cr{GMS}</>} field="net_weight_g" ordering={ordering} onSort={sort} />
                <SortableTh label="Ornament" field="ornament__name" ordering={ordering} onSort={sort} />
                <th className={STICKY_TH}>Order</th>
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
                  <td className={bodyTd}>{formatGramsValue(e.gross_weight_g)}</td>
                  <td className={bodyTd}>{e.carat}kt</td>
                  <td className={`${bodyTd} font-medium text-dr`}>{e.direction === "dr" ? formatGramsValue(e.net_weight_g) : ""}</td>
                  <td className={`${bodyTd} font-medium text-cr`}>{e.direction === "cr" ? formatGramsValue(e.net_weight_g) : ""}</td>
                  <td className={`${bodyTd} text-gray-600`}>{e.ornament_name || "—"}</td>
                  <td className={`${bodyTd} text-gray-600`}>{e.order_number || "—"}</td>
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
          kind="gold"
          entry={archiving}
          onClose={() => setArchiving(null)}
          onDone={() => { setArchiving(null); reload(); }}
        />
      )}

      {entry && (
        <GoldEntryForm
          entry={entry}
          karigars={karigars}
          onClose={() => setEntry(null)}
          onSaved={() => { setEntry(null); reload(); }}
        />
      )}
    </div>
  );
}

function GoldEntryForm({ entry, karigars, onClose, onSaved }) {
  const isEdit = Boolean(entry.id);
  const direction = entry.direction;
  const isReceive = direction === "cr";
  const calendar = useSettingsStore((s) => s.calendar);
  const { register, handleSubmit, control, setValue, getValues } = useForm({
    defaultValues: {
      karigar: entry.karigar ?? "",
      order_number: entry.order_number ?? "",
      gross_weight_g: entry.gross_weight_g ?? "",
      carat: entry.carat ?? 24,
      ornament: entry.ornament ?? "",
      remarks: entry.remarks ?? "",
      entry_date: entry.entry_date ?? new Date().toISOString().slice(0, 10),
    },
  });
  const gross = useWatch({ control, name: "gross_weight_g" });
  const carat = useWatch({ control, name: "carat" });
  const entryDate = useWatch({ control, name: "entry_date" });
  const [photo, setPhoto] = useState(null);
  const [error, setError] = useState("");
  const [addingOrnament, setAddingOrnament] = useState(false);
  const { data: ornData, refresh: refreshOrnaments } = useFetch("/ornaments/", { page_size: 200 });
  const ornaments = ornData?.results ?? [];

  // The ornament/order <select> options are fetched below (async), so they
  // aren't in the DOM when react-hook-form applies defaultValues at mount. On
  // edit the native select therefore can't show the saved value — re-sync it
  // once the list arrives. (Also defaults a new receipt's ornament to "Gold".)
  useEffect(() => {
    if (!ornaments.length) return;
    if (isEdit && entry.ornament) {
      setValue("ornament", String(entry.ornament));
    } else if (!isEdit && isReceive && !getValues("ornament")) {
      const gold = ornaments.find((o) => o.name.toLowerCase() === "gold");
      if (gold) setValue("ornament", String(gold.id));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ornData]);

  const onSubmit = async (v) => {
    setError("");
    try {
      if (isEdit) {
        // JSON PATCH for fields; photo (if changed) via the dedicated endpoint.
        const payload = {
          gross_weight_g: v.gross_weight_g,
          carat: Number(v.carat),
          entry_date: v.entry_date,
          remarks: v.remarks || "",
          order_number: v.order_number || "",
        };
        if (isReceive && v.ornament) payload.ornament = Number(v.ornament);
        await api.patch(`/gold-entries/${entry.id}/`, payload);
        if (photo) {
          const pf = new FormData();
          pf.append("photo", photo);
          await api.post(`/gold-entries/${entry.id}/photo/`, pf);
        }
      } else {
        // Create is multipart (Cr receipts may include an ornament photo).
        const fd = new FormData();
        fd.append("karigar", v.karigar);
        fd.append("direction", direction);
        fd.append("gross_weight_g", v.gross_weight_g);
        fd.append("carat", v.carat);
        fd.append("entry_date", v.entry_date);
        fd.append("remarks", v.remarks || "");
        fd.append("order_number", v.order_number || "");
        if (isReceive && v.ornament) fd.append("ornament", v.ornament);
        if (photo) fd.append("photo", photo);
        await api.post("/gold-entries/", fd);
      }
      onSaved();
    } catch (e) {
      setError(apiError(e));
    }
  };

  const title = isEdit ? "Edit gold entry" : isReceive ? "Receive ornament (Cr)" : "Issue gold (Dr)";

  return (
    <Modal open onClose={onClose} title={title} wide>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {error && <ErrorState message={error} />}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Karigar" required>
            <select className="input" {...register("karigar", { required: true })} disabled={isEdit}>
              <option value="">Select karigar…</option>
              {karigars.map((k) => <option key={k.id} value={k.id}>{k.full_name}</option>)}
            </select>
          </Field>
          <Field label={`Date (${calendar})`} required>
            <DateInput calendar={calendar} value={entryDate}
              onChange={(v) => setValue("entry_date", v)} />
          </Field>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Field label="Gross weight (g)" required>
            <input className="input" type="number" step="0.001" min="0.001" {...register("gross_weight_g", { required: true })} />
          </Field>
          <Field label="Carat" required>
            <select className="input" {...register("carat", { required: true })}>
              <option value={24}>24kt</option>
              <option value={22}>22kt</option>
            </select>
          </Field>
          <Field label="Net weight (g)">
            <input className="input bg-gray-50" value={netPreview(gross, carat)} readOnly tabIndex={-1} />
          </Field>
        </div>

        {isReceive && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Ornament received" required>
              <div className="flex gap-2">
                <select className="input" {...register("ornament")}>
                  <option value="">Select ornament…</option>
                  {ornaments.filter((o) => o.is_active).map((o) => (
                    <option key={o.id} value={o.id}>{o.name}</option>
                  ))}
                </select>
                <button
                  type="button"
                  className="btn-secondary shrink-0"
                  title="Add a new ornament"
                  onClick={() => setAddingOrnament(true)}
                >
                  <Plus size={16} />
                </button>
              </div>
            </Field>
            <Field label="Photo of ornament">
              <input
                className="input"
                type="file"
                accept="image/*"
                capture="environment"
                onChange={(e) => setPhoto(e.target.files?.[0] ?? null)}
              />
            </Field>
          </div>
        )}

        {/* Just the number written on the paperwork — a label on this entry,
            not a link to anything. */}
        <Field label="Order number (optional)">
          <input className="input" placeholder="e.g. ORD-1002" {...register("order_number")} />
        </Field>

        <Field label="Remarks">
          <textarea className="input" rows={2} {...register("remarks")} />
        </Field>

        {isEdit && entry.photo && (
          <img src={entry.photo} alt="" className="h-24 w-24 rounded-lg object-cover" />
        )}

        <div className="flex justify-end gap-2 pt-2">
          <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary">Save</button>
        </div>
      </form>

      {/* Quick-add ornament without leaving the receive form. */}
      {addingOrnament && (
        <QuickAddOrnament
          onClose={() => setAddingOrnament(false)}
          onAdded={async (id) => {
            setAddingOrnament(false);
            await refreshOrnaments();
            setValue("ornament", String(id)); // select the new ornament
          }}
        />
      )}
    </Modal>
  );
}

function QuickAddOrnament({ onClose, onAdded }) {
  const { register, handleSubmit } = useForm({ defaultValues: { name: "", description: "" } });
  const [error, setError] = useState("");

  const onSubmit = async (v) => {
    setError("");
    try {
      const { data } = await api.post("/ornaments/", { name: v.name, description: v.description });
      onAdded(data.id);
    } catch (e) {
      setError(apiError(e));
    }
  };

  return (
    <Modal open onClose={onClose} title="Add ornament">
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {error && <ErrorState message={error} />}
        <Field label="Name" required>
          <input className="input" autoFocus {...register("name", { required: true })} />
        </Field>
        <Field label="Description">
          <input className="input" {...register("description")} />
        </Field>
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary">Add &amp; select</button>
        </div>
      </form>
    </Modal>
  );
}
