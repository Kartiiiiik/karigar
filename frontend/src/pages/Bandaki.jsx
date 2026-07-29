import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useForm, useWatch, useFieldArray } from "react-hook-form";
import { Plus, Pencil, UserPlus, HandCoins, Trash2 } from "lucide-react";
import api, { apiError } from "../lib/api";
import { useFetch } from "../hooks/useFetch";
import {
  PageHeader, Spinner, EmptyState, ErrorState, Modal, Field, Badge, SortableTh,
  STICKY_TH, STICKY_TH_RIGHT,
} from "../components/ui";
import DateInput from "../components/DateInput";
import Select, { FormSelect } from "../components/Select";
import { formatAmount, formatGramsValue } from "../lib/format";
import { formatDate } from "../lib/date";
import { useSettingsStore } from "../store/settings";

// Unit label for money column headers (keeps the rows unit-free).
const NPR = <sub className="ml-0.5 text-[10px] font-normal text-gray-400">npr</sub>;

const PERIOD_SHORT = { monthly: "mo", yearly: "yr" };

export default function Bandaki() {
  const [tab, setTab] = useState("loans");

  return (
    <div className="flex h-full flex-col">
      <div className="hidden sm:block">
        <PageHeader
          title="Bandaki"
          subtitle="Gold loans — money lent against gold. Interest accrues by the day and is shown live."
        />
      </div>

      <div className="mb-3 flex shrink-0 gap-2 border-b border-gray-200">
        {["loans", "customers"].map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium capitalize ${
              tab === t ? "border-brand-600 text-brand-700" : "border-transparent text-gray-500"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="flex min-h-0 flex-1 flex-col">
        {tab === "loans" ? <Loans /> : <Customers />}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Loans
// ---------------------------------------------------------------------------
function Loans() {
  const calendar = useSettingsStore((s) => s.calendar);
  const dateFormat = useSettingsStore((s) => s.dateFormat);
  const [filters, setFilters] = useState({ customer: "", is_active: "true", search: "" });
  const [ordering, setOrdering] = useState("-loan_date");

  const clean = Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== ""));
  const cleanKey = JSON.stringify(clean);
  const listParams = useMemo(
    () => ({ page_size: 1000, ordering, ...clean }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [ordering, cleanKey],
  );
  const { data, loading, error, refresh } = useFetch("/bandaki/loans/", listParams);
  const { data: custData, refresh: refreshCustomers } = useFetch("/bandaki/customers/", { page_size: 1000 });
  // The shop's ornament list — shared with the gold receive-form.
  const { data: ornData } = useFetch("/ornaments/", { page_size: 200 });
  const ornaments = ornData?.results ?? [];
  const [loan, setLoan] = useState(null);       // edit form
  const [detail, setDetail] = useState(null);   // row clicked — payment history
  const [paying, setPaying] = useState(null);   // receive-payment form
  const customers = custData?.results ?? [];
  const items = data?.results ?? [];
  const count = data?.count ?? 0;

  // Open the new-loan form when arrived via the dashboard quick action.
  const [sp, setSp] = useSearchParams();
  useEffect(() => {
    if (sp.get("action") === "new") {
      setLoan({});
      sp.delete("action");
      setSp(sp, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const sort = (field) => setOrdering((o) => (o === field ? `-${field}` : field));

  // Footer totals across the loaded rows (all rows fetched in one page).
  const totals = items.reduce(
    (acc, l) => {
      acc.principal += Number(l.gross_amount);
      acc.interest += Number(l.interest_amount);
      acc.paid += Number(l.total_paid ?? 0);
      acc.total += Number(l.total_amount);
      return acc;
    },
    { principal: 0, interest: 0, paid: 0, total: 0 },
  );

  // Sticky-cell classes + total-row cells. Columns: Date, Customer, Lent,
  // Rate, Interest, Paid, Outstanding, Remarks, action — money right-aligned
  // so the digits line up down the column.
  const bodyTd = "whitespace-nowrap border-b border-gray-100 px-3 py-2";
  const numTd = `${bodyTd} text-right tabular-nums`;
  const footTd = "sticky bottom-0 z-20 h-10 whitespace-nowrap border-t border-amber-200 bg-amber-50 px-3 font-semibold text-gray-800";
  const totalCells = [
    { v: `Total (${count})` },
    { v: "" },
    { v: formatAmount(totals.principal), num: true },
    { v: "" },
    { v: formatAmount(totals.interest), num: true },
    { v: formatAmount(totals.paid), num: true },
    { v: formatAmount(totals.total), num: true },
    { v: "" },
    { v: "" },
  ];

  // A write from any of the three panels invalidates the row figures.
  const afterWrite = () => refresh();

  return (
    <div className="flex h-full flex-col">
      <div className="mb-3 shrink-0 space-y-2">
        <div className="flex gap-2">
          <button className="btn-primary flex-1 sm:flex-none" onClick={() => setLoan({})}>
            <Plus size={16} /> New bandaki
          </button>
        </div>
        <div className="flex flex-wrap gap-2 sm:justify-end">
          <Select
            className="min-w-0 flex-1 sm:w-48 sm:flex-none"
            aria-label="Filter by customer"
            value={filters.customer}
            onChange={(v) => setFilters((f) => ({ ...f, customer: v }))}
            options={[
              { value: "", label: "All customers" },
              ...customers.map((c) => ({ value: c.id, label: c.name })),
            ]}
          />
          <Select
            className="w-28 shrink-0 sm:w-36"
            aria-label="Filter by status"
            value={filters.is_active}
            onChange={(v) => setFilters((f) => ({ ...f, is_active: v }))}
            options={[
              { value: "", label: "All" },
              { value: "true", label: "Active" },
              { value: "false", label: "Closed" },
            ]}
          />
          <input
            className="input w-full sm:w-56"
            placeholder="Search customer, phone, remarks…"
            value={filters.search}
            onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value }))}
          />
        </div>
      </div>

      {error && <ErrorState message={error} />}
      {loading && !data ? (
        <Spinner />
      ) : count === 0 ? (
        <EmptyState message="No bandaki loans yet." />
      ) : (
        <div className="min-h-0 flex-1 overflow-auto rounded-xl border border-gray-200 bg-white">
          <table className="min-w-full border-separate border-spacing-0 text-sm">
            <thead className="text-left text-xs uppercase text-gray-500">
              <tr>
                <SortableTh label="Date" field="loan_date" ordering={ordering} onSort={sort} />
                <SortableTh label="Customer" field="customer__name" ordering={ordering} onSort={sort} />
                <SortableTh label={<>Lent{NPR}</>} field="gross_amount" ordering={ordering} onSort={sort} align="right" />
                <SortableTh label="Rate" field="interest_rate" ordering={ordering} onSort={sort} align="right" />
                <th className={STICKY_TH_RIGHT}>Interest{NPR}</th>
                <th className={STICKY_TH_RIGHT}>Paid{NPR}</th>
                <th className={STICKY_TH_RIGHT}>Outstanding{NPR}</th>
                <th className={STICKY_TH}>Remarks</th>
                <th className={STICKY_TH}></th>
              </tr>
            </thead>
            <tbody>
              {items.map((l) => (
                <tr
                  key={l.id}
                  className={`cursor-pointer hover:bg-gray-50 ${l.is_active ? "" : "opacity-60"}`}
                  onClick={() => setDetail(l)}
                  title="View payment history"
                >
                  {/* Date carries the elapsed days beneath it — same fact,
                      one column instead of two. */}
                  <td className={`${bodyTd} text-gray-600`}>
                    {formatDate(l.loan_date, calendar, { format: dateFormat })}
                    <span className="block text-xs text-gray-400">{l.days_elapsed} days</span>
                  </td>
                  <td className={bodyTd}>
                    <span className="inline-flex items-center gap-2">
                      {l.customer_name}
                      {!l.is_active && <Badge tone="gray">Closed</Badge>}
                    </span>
                    {l.payment_count > 0 && (
                      <span className="block text-xs text-gray-400">
                        {l.payment_count} payment{l.payment_count > 1 ? "s" : ""}
                      </span>
                    )}
                  </td>
                  <td className={numTd}>{formatAmount(l.gross_amount)}</td>
                  <td className={`${numTd} text-gray-600`}>
                    {Number(l.interest_rate)}%
                    <span className="block text-xs text-gray-400">
                      per {PERIOD_SHORT[l.interest_period]}
                    </span>
                  </td>
                  <td className={`${numTd} text-dr`}>{formatAmount(l.interest_amount)}</td>
                  <td className={`${numTd} text-cr`}>
                    {Number(l.total_paid ?? 0) > 0 ? formatAmount(l.total_paid) : <span className="text-gray-300">—</span>}
                  </td>
                  <td className={`${numTd} font-semibold text-gray-900`}>{formatAmount(l.total_amount)}</td>
                  <td className={`${bodyTd} text-gray-500`}>{l.remarks || "—"}</td>
                  <td className={`${bodyTd} text-right`} onClick={(e) => e.stopPropagation()}>
                    <div className="flex items-center justify-end gap-1">
                      {l.is_active && (
                        <button
                          className="rounded p-1 text-gray-400 hover:bg-green-50 hover:text-cr"
                          title="Receive payment"
                          onClick={() => setPaying(l)}
                        >
                          <HandCoins size={16} />
                        </button>
                      )}
                      <button
                        className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-brand-600"
                        title="Edit loan"
                        onClick={() => setLoan(l)}
                      >
                        <Pencil size={15} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                {totalCells.map((c, i) => (
                  <td key={i} className={`${footTd} ${c.num ? "text-right tabular-nums" : ""}`}>
                    {c.v}
                  </td>
                ))}
              </tr>
            </tfoot>
          </table>
        </div>
      )}

      {loan && (
        <LoanForm
          loan={loan}
          customers={customers}
          ornaments={ornaments}
          refreshCustomers={refreshCustomers}
          onClose={() => setLoan(null)}
          onSaved={() => { setLoan(null); afterWrite(); }}
        />
      )}

      {paying && (
        <PaymentForm
          loan={paying}
          onClose={() => setPaying(null)}
          onSaved={() => { setPaying(null); afterWrite(); }}
        />
      )}

      {detail && (
        <LoanDetail
          loan={detail}
          ornaments={ornaments}
          onClose={() => setDetail(null)}
          onChanged={afterWrite}
        />
      )}

    </div>
  );
}

// ---------------------------------------------------------------------------
// Receive payment
// ---------------------------------------------------------------------------
function PaymentForm({ loan, onClose, onSaved }) {
  const calendar = useSettingsStore((s) => s.calendar);
  const { register, handleSubmit, control, setValue } = useForm({
    defaultValues: {
      payment_date: new Date().toISOString().slice(0, 10),
      amount: "",
      remarks: "",
    },
  });
  const paymentDate = useWatch({ control, name: "payment_date" });
  const amount = useWatch({ control, name: "amount" });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const outstanding = Number(loan.total_amount);
  const interestDue = Number(loan.interest_amount);

  // Mirror the backend waterfall so the owner can see where the money will
  // land before committing. The server stays the authority.
  const entered = Number(amount) || 0;
  const toInterest = Math.min(entered, interestDue);
  const toPrincipal = Math.max(0, Math.min(entered - toInterest, Number(loan.principal_outstanding)));
  const remaining = Math.max(0, outstanding - entered);
  const over = entered > outstanding;

  const onSubmit = async (v) => {
    setError("");
    setSaving(true);
    try {
      await api.post(`/bandaki/loans/${loan.id}/payments/`, {
        payment_date: v.payment_date,
        amount: v.amount,
        remarks: v.remarks || "",
      });
      onSaved();
    } catch (e) {
      setError(apiError(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open onClose={onClose} title={`Receive payment — ${loan.customer_name}`}>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {error && <ErrorState message={error} />}

        <div className="rounded-lg bg-gray-50 p-3 text-sm">
          <SummaryRow label="Principal outstanding" value={loan.principal_outstanding} />
          <SummaryRow label="Interest owed" value={loan.interest_amount} tone="dr" />
          <SummaryRow label="Total outstanding" value={loan.total_amount} bold />
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Amount received (NPR)" required>
            <input className="input" type="number" step="0.01" min="0.01" autoFocus
              {...register("amount", { required: true })} />
          </Field>
          <Field label={`Payment date (${calendar})`} required>
            <DateInput calendar={calendar} value={paymentDate}
              onChange={(v) => setValue("payment_date", v)} />
          </Field>
        </div>

        <button
          type="button"
          className="text-xs text-brand-600 hover:underline"
          onClick={() => setValue("amount", loan.total_amount)}
        >
          Pay off in full ({formatAmount(loan.total_amount)})
        </button>

        {entered > 0 && (
          <div className={`rounded-lg border p-3 text-sm ${over ? "border-danger/30 bg-danger-soft" : "border-gray-200 bg-white"}`}>
            {over ? (
              <p className="text-danger-text">
                That is {formatAmount(entered - outstanding)} more than this loan owes.
              </p>
            ) : (
              <>
                <p className="mb-2 text-xs uppercase text-gray-500">Will be applied as</p>
                <SummaryRow label="Towards interest" value={toInterest} tone="dr" />
                <SummaryRow label="Towards principal" value={toPrincipal} />
                <SummaryRow
                  label={remaining <= 0 ? "Loan fully settled — will close" : "Still owing after this"}
                  value={remaining}
                  bold
                />
              </>
            )}
          </div>
        )}

        <Field label="Remarks">
          <textarea className="input" rows={2} {...register("remarks")} />
        </Field>

        <div className="flex justify-end gap-2 pt-2">
          <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary" disabled={saving || over}>
            {saving ? "Saving…" : "Record payment"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

/** One label/amount line inside a summary block. */
function SummaryRow({ label, value, tone, bold }) {
  return (
    <div className="flex items-baseline justify-between py-0.5">
      <span className="text-gray-500">{label}</span>
      <span
        className={`tabular-nums ${bold ? "font-semibold text-gray-900" : "font-medium"} ${
          tone === "dr" ? "text-dr" : tone === "cr" ? "text-cr" : ""
        }`}
      >
        {formatAmount(value)}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Loan detail — the row's payment history
// ---------------------------------------------------------------------------
function LoanDetail({ loan: initial, ornaments, onClose, onChanged }) {
  const calendar = useSettingsStore((s) => s.calendar);
  const dateFormat = useSettingsStore((s) => s.dateFormat);
  const [loan, setLoan] = useState(initial);
  const [paying, setPaying] = useState(false);
  const [removing, setRemoving] = useState(null);
  const { data, loading, error, refresh } = useFetch(`/bandaki/loans/${initial.id}/payments/`);
  const payments = data ?? [];

  // Re-read the loan too: every payment write moves the settlement figures.
  const reload = async () => {
    const { data: fresh } = await api.get(`/bandaki/loans/${initial.id}/`);
    setLoan(fresh);
    await refresh();
    onChanged();
  };

  const td = "whitespace-nowrap border-b border-gray-100 px-3 py-2 text-sm";

  return (
    <Modal
      open
      onClose={onClose}
      // The row behind this dialog already carries the figures, so the title
      // only has to say *which* loan — a customer can have several running.
      title={`${loan.customer_name} — ${formatAmount(loan.gross_amount)} taken ${formatDate(loan.loan_date, calendar, { format: dateFormat })}`}
      wide
    >
      <div className="space-y-5">
        <div>
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-gray-700">Payments received</h3>
            {loan.is_active && (
              <button className="btn-primary py-1 text-sm" onClick={() => setPaying(true)}>
                <HandCoins size={15} /> Receive payment
              </button>
            )}
          </div>

          {error && <ErrorState message={error} />}
          {loading && !data ? (
            <Spinner />
          ) : payments.length === 0 ? (
            <EmptyState message="No payments received yet." />
          ) : (
            <div className="overflow-x-auto rounded-lg border border-gray-200">
              <table className="min-w-full border-separate border-spacing-0">
                <thead className="text-left text-xs uppercase text-gray-500">
                  <tr>
                    <th className={STICKY_TH}>Date</th>
                    <th className={STICKY_TH}>Received{NPR}</th>
                    <th className={STICKY_TH}>To interest{NPR}</th>
                    <th className={STICKY_TH}>To principal{NPR}</th>
                    <th className={STICKY_TH}>Owing after{NPR}</th>
                    <th className={STICKY_TH}>Remarks</th>
                    <th className={STICKY_TH}></th>
                  </tr>
                </thead>
                <tbody>
                  {payments.map((p) => (
                    <tr key={p.id} className="hover:bg-gray-50">
                      <td className={`${td} text-gray-600`}>
                        {formatDate(p.payment_date, calendar, { format: dateFormat })}
                      </td>
                      <td className={`${td} font-semibold text-cr`}>{formatAmount(p.amount)}</td>
                      <td className={`${td} text-dr`}>{formatAmount(p.interest_part)}</td>
                      <td className={td}>{formatAmount(p.principal_part)}</td>
                      <td className={`${td} font-medium`}>{formatAmount(p.outstanding_after)}</td>
                      <td className={`${td} text-gray-500`}>{p.remarks || "—"}</td>
                      <td className={`${td} text-right`}>
                        <button
                          className="rounded p-1 text-gray-400 hover:bg-danger-soft hover:text-danger"
                          title="Delete payment"
                          onClick={() => setRemoving(p)}
                        >
                          <Trash2 size={15} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {payments.length > 0 && (
            <p className="mt-2 text-xs text-gray-400">
              Each payment clears the interest owed on that day first; whatever is left cuts the
              principal, so later interest is charged on the smaller amount.
            </p>
          )}
        </div>

        <PledgedGold
          loan={loan}
          ornaments={ornaments}
          onChanged={(fresh) => { setLoan(fresh); onChanged(); }}
        />
      </div>

      {paying && (
        <PaymentForm
          loan={loan}
          onClose={() => setPaying(false)}
          onSaved={() => { setPaying(false); reload(); }}
        />
      )}

      {removing && (
        <DeletePayment
          payment={removing}
          onClose={() => setRemoving(null)}
          onDone={() => { setRemoving(null); reload(); }}
        />
      )}
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Pledged gold panel — what the shop is holding, released piece by piece
// ---------------------------------------------------------------------------
function PledgedGold({ loan, ornaments, onChanged }) {
  const calendar = useSettingsStore((s) => s.calendar);
  const dateFormat = useSettingsStore((s) => s.dateFormat);
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState("");
  const items = loan.items ?? [];
  const held = items.filter((i) => i.is_held);

  // Every item write returns the re-derived loan, so one call keeps the whole
  // panel — held weight included — in step.
  const setReturned = async (item) => {
    setError("");
    setBusy(item.id);
    try {
      const { data } = await api.patch(`/bandaki/items/${item.id}/`, {
        returned_on: item.is_held ? new Date().toISOString().slice(0, 10) : null,
      });
      onChanged(data);
    } catch (e) {
      setError(apiError(e));
    } finally {
      setBusy(null);
    }
  };

  const td = "whitespace-nowrap border-b border-gray-100 px-3 py-2 text-sm";

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-700">
          Gold held{" "}
          {held.length > 0 && (
            <span className="font-normal text-gray-400">
              · {formatGramsValue(loan.net_weight_held_g)} g net
            </span>
          )}
        </h3>
        <button className="btn-secondary py-1 text-sm" onClick={() => setAdding(true)}>
          <Plus size={15} /> Add piece
        </button>
      </div>

      {error && <ErrorState message={error} />}

      {items.length === 0 ? (
        <EmptyState message="No gold recorded against this loan." />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="min-w-full border-separate border-spacing-0">
            <thead className="text-left text-xs uppercase text-gray-500">
              <tr>
                <th className={STICKY_TH}>Item</th>
                <th className={STICKY_TH_RIGHT}>Qty</th>
                <th className={STICKY_TH_RIGHT}>Gross g</th>
                <th className={STICKY_TH}>Carat</th>
                <th className={STICKY_TH_RIGHT}>Net g</th>
                <th className={STICKY_TH}>Status</th>
                <th className={STICKY_TH}></th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => (
                <tr key={it.id} className={`hover:bg-gray-50 ${it.is_held ? "" : "opacity-60"}`}>
                  <td className={td}>
                    {it.ornament_name}
                    {it.description && (
                      <span className="block text-xs text-gray-400">{it.description}</span>
                    )}
                  </td>
                  <td className={`${td} text-right tabular-nums`}>{it.quantity}</td>
                  <td className={`${td} text-right tabular-nums text-gray-600`}>
                    {formatGramsValue(it.gross_weight_g)}
                  </td>
                  <td className={`${td} text-gray-600`}>{it.carat}kt</td>
                  <td className={`${td} text-right font-medium tabular-nums`}>
                    {formatGramsValue(it.net_weight_g)}
                  </td>
                  <td className={td}>
                    {it.is_held ? (
                      <Badge tone="amber">Held</Badge>
                    ) : (
                      <span className="text-xs text-gray-500">
                        Returned {formatDate(it.returned_on, calendar, { format: dateFormat })}
                      </span>
                    )}
                  </td>
                  <td className={`${td} text-right`}>
                    {/* Words, not icons: "give it back" and "I mis-clicked"
                        are too close in meaning for two rotation glyphs. */}
                    <button
                      className="rounded px-2 py-1 text-xs font-medium text-gray-500 hover:bg-gray-100 hover:text-brand-600 disabled:opacity-40"
                      disabled={busy === it.id}
                      onClick={() => setReturned(it)}
                    >
                      {it.is_held ? "Return" : "Undo"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {items.length > 0 && (
        <p className="mt-2 text-xs text-gray-400">
          Returning a piece records the date rather than deleting the row, so the loan keeps a
          record of everything that was ever held against it.
        </p>
      )}

      {adding && (
        <AddPledgedItem
          loan={loan}
          ornaments={ornaments}
          onClose={() => setAdding(false)}
          onAdded={(fresh) => { setAdding(false); onChanged(fresh); }}
        />
      )}
    </div>
  );
}

function AddPledgedItem({ loan, ornaments, onClose, onAdded }) {
  const { register, handleSubmit, control } = useForm({
    defaultValues: { ornament: "", quantity: 1, gross_weight_g: "", carat: 22, description: "" },
  });
  const gross = useWatch({ control, name: "gross_weight_g" });
  const carat = useWatch({ control, name: "carat" });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const onSubmit = async (v) => {
    setError("");
    setSaving(true);
    try {
      const { data } = await api.post(`/bandaki/loans/${loan.id}/items/`, {
        ornament: Number(v.ornament),
        quantity: Number(v.quantity) || 1,
        gross_weight_g: v.gross_weight_g,
        carat: Number(v.carat),
        description: v.description || "",
      });
      onAdded(data);
    } catch (e) {
      setError(apiError(e));
      setSaving(false);
    }
  };

  return (
    <Modal open onClose={onClose} title="Add pledged gold">
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {error && <ErrorState message={error} />}
        <Field label="Item" required>
          <FormSelect
            control={control}
            name="ornament"
            rules={{ required: true }}
            placeholder="Select item…"
            options={ornaments.map((o) => ({ value: o.id, label: o.name }))}
          />
        </Field>
        <div className="grid grid-cols-3 gap-3">
          <Field label="Quantity" required>
            <input className="input" type="number" min="1" step="1"
              {...register("quantity", { required: true })} />
          </Field>
          <Field label="Gross (g)" required>
            <input className="input" type="number" step="0.001" min="0.001"
              {...register("gross_weight_g", { required: true })} />
          </Field>
          <Field label="Carat" required>
            <FormSelect control={control} name="carat" options={CARAT_OPTIONS} />
          </Field>
        </div>
        <p className="text-sm text-gray-500">
          Net weight{" "}
          <span className="font-semibold tabular-nums text-gray-800">
            {formatGramsValue(netOf(gross, carat))} g
          </span>
        </p>
        <Field label="Description">
          <input className="input" placeholder="e.g. thick chain with locket"
            {...register("description")} />
        </Field>
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary" disabled={saving}>
            {saving ? "Saving…" : "Add piece"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function DeletePayment({ payment, onClose, onDone }) {
  const calendar = useSettingsStore((s) => s.calendar);
  const dateFormat = useSettingsStore((s) => s.dateFormat);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const run = async () => {
    setError("");
    setSaving(true);
    try {
      await api.delete(`/bandaki/payments/${payment.id}/`);
      onDone();
    } catch (e) {
      setError(apiError(e));
      setSaving(false);
    }
  };

  return (
    <Modal open onClose={onClose} title="Delete this payment?">
      <div className="space-y-4">
        {error && <ErrorState message={error} />}
        <p className="text-sm text-gray-600">
          Removing the {formatAmount(payment.amount)} received on{" "}
          {formatDate(payment.payment_date, calendar, { format: dateFormat })} will re-work every
          payment after it, and reopen the loan if it no longer comes out settled.
        </p>
        <div className="flex justify-end gap-2">
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-danger" onClick={run} disabled={saving}>
            {saving ? "Deleting…" : "Delete payment"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

function LoanForm({ loan, customers, ornaments, refreshCustomers, onClose, onSaved }) {
  const isEdit = Boolean(loan.id);
  const calendar = useSettingsStore((s) => s.calendar);
  const { register, handleSubmit, control, setValue } = useForm({
    defaultValues: {
      // Select values are strings, matching what the native select reported.
      customer: loan.customer != null ? String(loan.customer) : "",
      gross_amount: loan.gross_amount ?? "",
      interest_rate: loan.interest_rate ?? "",
      interest_period: loan.interest_period ?? "monthly",
      remarks: loan.remarks ?? "",
      loan_date: loan.loan_date ?? new Date().toISOString().slice(0, 10),
      is_active: String(loan.is_active ?? true),
      items: [],
    },
  });
  const loanDate = useWatch({ control, name: "loan_date" });
  const [error, setError] = useState("");
  const [addingCustomer, setAddingCustomer] = useState(false);

  const onSubmit = async (v) => {
    setError("");
    const payload = {
      customer: Number(v.customer),
      loan_date: v.loan_date,
      gross_amount: v.gross_amount,
      interest_rate: v.interest_rate,
      interest_period: v.interest_period,
      remarks: v.remarks || "",
    };
    try {
      if (isEdit) {
        await api.patch(`/bandaki/loans/${loan.id}/`, { ...payload, is_active: v.is_active });
      } else {
        // Gold and money change hands together, so the pieces go up with the
        // loan — the server writes both or neither.
        payload.items = (v.items ?? []).map((it) => ({
          ornament: Number(it.ornament),
          quantity: Number(it.quantity) || 1,
          gross_weight_g: it.gross_weight_g,
          carat: Number(it.carat),
          description: it.description || "",
        }));
        await api.post("/bandaki/loans/", payload);
      }
      onSaved();
    } catch (e) {
      setError(apiError(e));
    }
  };

  return (
    <Modal open onClose={onClose} title={isEdit ? "Edit bandaki" : "New bandaki (gold loan)"} wide>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {error && <ErrorState message={error} />}

        <Field label="Customer" required>
          <div className="flex gap-2">
            <FormSelect
              control={control}
              name="customer"
              rules={{ required: true }}
              placeholder="Select customer…"
              options={customers.map((c) => ({ value: c.id, label: c.name }))}
            />
            <button
              type="button"
              className="btn-secondary shrink-0"
              title="Add a new customer"
              onClick={() => setAddingCustomer(true)}
            >
              <UserPlus size={16} />
            </button>
          </div>
        </Field>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Gross amount (NPR)" required>
            <input className="input" type="number" step="0.01" min="0.01"
              {...register("gross_amount", { required: true })} />
          </Field>
          <Field label={`Loan date (${calendar})`} required>
            <DateInput calendar={calendar} value={loanDate}
              onChange={(v) => setValue("loan_date", v)} />
          </Field>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Interest rate (%)" required>
            <input className="input" type="number" step="0.001" min="0"
              {...register("interest_rate", { required: true })} />
          </Field>
          <Field label="Interest period" required>
            <FormSelect
              control={control}
              name="interest_period"
              rules={{ required: true }}
              options={[
                { value: "monthly", label: "Monthly" },
                { value: "yearly", label: "Yearly" },
              ]}
            />
          </Field>
        </div>

        {/* Pledged gold is captured with a new loan. On an existing one it is
            managed from the detail panel, where returns live too. */}
        {!isEdit && (
          <PledgedItemsFields control={control} register={register} ornaments={ornaments} />
        )}

        <Field label="Remarks">
          <textarea className="input" rows={2} {...register("remarks")} />
        </Field>

        {isEdit && (
          <Field label="Loan status">
            <FormSelect
              control={control}
              name="is_active"
              options={[
                { value: true, label: "Active (still owed)" },
                { value: false, label: "Closed (repaid)" },
              ]}
            />
          </Field>
        )}

        <div className="flex justify-end gap-2 pt-2">
          <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary">Save</button>
        </div>
      </form>

      {/* Quick-add customer without leaving the loan form. */}
      {addingCustomer && (
        <QuickAddCustomer
          onClose={() => setAddingCustomer(false)}
          onAdded={async (id) => {
            setAddingCustomer(false);
            await refreshCustomers();
            setValue("customer", String(id)); // select the new customer
          }}
        />
      )}
    </Modal>
  );
}

// Carat options mirror the gold ledger; net weight is gross x carat/24.
const CARAT_OPTIONS = [
  { value: 22, label: "22kt" },
  { value: 24, label: "24kt" },
];

const netOf = (gross, carat) =>
  (Number(gross) || 0) * ((Number(carat) || 22) / 24);

/** Repeatable rows for the gold a customer is handing over. */
function PledgedItemsFields({ control, register, ornaments }) {
  const { fields, append, remove } = useFieldArray({ control, name: "items" });
  const items = useWatch({ control, name: "items" }) ?? [];
  const totalNet = items.reduce(
    (sum, it) => sum + netOf(it?.gross_weight_g, it?.carat) * (Number(it?.quantity) || 1),
    0,
  );

  const addRow = () =>
    append({ ornament: "", quantity: 1, gross_weight_g: "", carat: 22, description: "" });

  return (
    <div className="rounded-lg border border-gray-200 p-3">
      <div className="mb-2 flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-gray-700">Gold pledged</p>
          <p className="text-xs text-gray-400">
            What the customer is handing over as security.
          </p>
        </div>
        <button type="button" className="btn-secondary py-1 text-sm" onClick={addRow}>
          <Plus size={15} /> Add piece
        </button>
      </div>

      {fields.length === 0 ? (
        <p className="py-2 text-sm text-gray-400">
          No pieces recorded. You can add them later from the loan.
        </p>
      ) : (
        <div className="space-y-2">
          {fields.map((f, i) => (
            <div key={f.id} className="grid grid-cols-12 items-end gap-2">
              <div className="col-span-12 sm:col-span-3">
                <label className="text-xs text-gray-500">Item</label>
                <FormSelect
                  control={control}
                  name={`items.${i}.ornament`}
                  rules={{ required: true }}
                  placeholder="Select…"
                  options={ornaments.map((o) => ({ value: o.id, label: o.name }))}
                />
              </div>
              <div className="col-span-3 sm:col-span-1">
                <label className="text-xs text-gray-500">Qty</label>
                <input className="input" type="number" min="1" step="1"
                  {...register(`items.${i}.quantity`, { required: true })} />
              </div>
              <div className="col-span-5 sm:col-span-2">
                <label className="text-xs text-gray-500">Gross g</label>
                <input className="input" type="number" step="0.001" min="0.001"
                  {...register(`items.${i}.gross_weight_g`, { required: true })} />
              </div>
              <div className="col-span-4 sm:col-span-2">
                <label className="text-xs text-gray-500">Carat</label>
                <FormSelect
                  control={control}
                  name={`items.${i}.carat`}
                  options={CARAT_OPTIONS}
                />
              </div>
              <div className="col-span-10 sm:col-span-3">
                <label className="text-xs text-gray-500">
                  Description{" "}
                  <span className="tabular-nums text-gray-400">
                    · net {formatGramsValue(netOf(items[i]?.gross_weight_g, items[i]?.carat))} g
                  </span>
                </label>
                <input className="input" placeholder="e.g. with locket"
                  {...register(`items.${i}.description`)} />
              </div>
              <div className="col-span-2 sm:col-span-1 pb-1 text-right">
                <button
                  type="button"
                  className="rounded p-1.5 text-gray-400 hover:bg-danger-soft hover:text-danger"
                  title="Remove this piece"
                  onClick={() => remove(i)}
                >
                  <Trash2 size={15} />
                </button>
              </div>
            </div>
          ))}
          <p className="pt-1 text-right text-sm text-gray-600">
            Total net held{" "}
            <span className="font-semibold tabular-nums text-gray-900">
              {formatGramsValue(totalNet)} g
            </span>
          </p>
        </div>
      )}
    </div>
  );
}

function QuickAddCustomer({ onClose, onAdded }) {
  const { register, handleSubmit } = useForm({
    defaultValues: { name: "", phone: "", location: "", remarks: "" },
  });
  const [error, setError] = useState("");

  const onSubmit = async (v) => {
    setError("");
    try {
      const { data } = await api.post("/bandaki/customers/", {
        name: v.name,
        phone: v.phone || "",
        location: v.location || "",
        remarks: v.remarks || "",
      });
      onAdded(data.id);
    } catch (e) {
      setError(apiError(e));
    }
  };

  return (
    <Modal open onClose={onClose} title="Add bandaki customer">
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {error && <ErrorState message={error} />}
        <Field label="Name" required>
          <input className="input" autoFocus {...register("name", { required: true })} />
        </Field>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Phone">
            <input className="input" {...register("phone")} />
          </Field>
          <Field label="Location">
            <input className="input" {...register("location")} />
          </Field>
        </div>
        <Field label="Remarks">
          <textarea className="input" rows={2} {...register("remarks")} />
        </Field>
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary">Add &amp; select</button>
        </div>
      </form>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Customers
// ---------------------------------------------------------------------------
function Customers() {
  const [search, setSearch] = useState("");
  const params = useMemo(
    () => ({ page_size: 1000, ...(search ? { search } : {}) }),
    [search],
  );
  const { data, loading, error, refresh } = useFetch("/bandaki/customers/", params);
  const [editing, setEditing] = useState(null);
  const items = data?.results ?? [];

  return (
    <div className="flex h-full flex-col">
      <div className="mb-4 flex shrink-0 flex-wrap items-center gap-2">
        <button className="btn-primary" onClick={() => setEditing({})}>
          <Plus size={16} /> New customer
        </button>
        <input
          className="input sm:ml-auto sm:w-64"
          placeholder="Search name, phone, location…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {error && <ErrorState message={error} />}
      {loading && !data ? (
        <Spinner />
      ) : items.length === 0 ? (
        <EmptyState message="No customers yet." />
      ) : (
        <div className="min-h-0 flex-1 overflow-auto rounded-xl border border-gray-200 bg-white">
          <table className="min-w-full border-separate border-spacing-0 text-sm">
            <thead className="text-left text-xs uppercase text-gray-500">
              <tr>
                <th className={STICKY_TH}>Name</th>
                <th className={STICKY_TH}>Phone</th>
                <th className={STICKY_TH}>Location</th>
                <th className={STICKY_TH}>Loans</th>
                <th className={STICKY_TH}>Remarks</th>
                <th className={STICKY_TH}></th>
              </tr>
            </thead>
            <tbody>
              {items.map((c) => (
                <tr key={c.id} className="hover:bg-gray-50">
                  <td className="whitespace-nowrap border-b border-gray-100 px-3 py-2.5 font-medium">{c.name}</td>
                  <td className="whitespace-nowrap border-b border-gray-100 px-3 py-2.5 text-gray-600">{c.phone || "—"}</td>
                  <td className="whitespace-nowrap border-b border-gray-100 px-3 py-2.5 text-gray-600">{c.location || "—"}</td>
                  <td className="whitespace-nowrap border-b border-gray-100 px-3 py-2.5 text-gray-600">{c.loan_count}</td>
                  <td className="border-b border-gray-100 px-3 py-2.5 text-gray-500">{c.remarks || "—"}</td>
                  <td className="whitespace-nowrap border-b border-gray-100 px-3 py-2.5 text-right">
                    <button className="text-gray-400 hover:text-brand-600" onClick={() => setEditing(c)}>
                      <Pencil size={15} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editing && (
        <CustomerForm
          customer={editing}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); refresh(); }}
        />
      )}
    </div>
  );
}

function CustomerForm({ customer, onClose, onSaved }) {
  const isEdit = Boolean(customer.id);
  const { register, handleSubmit } = useForm({
    defaultValues: {
      name: customer.name ?? "",
      phone: customer.phone ?? "",
      location: customer.location ?? "",
      remarks: customer.remarks ?? "",
    },
  });
  const [error, setError] = useState("");

  const onSubmit = async (v) => {
    setError("");
    const payload = {
      name: v.name,
      phone: v.phone || "",
      location: v.location || "",
      remarks: v.remarks || "",
    };
    try {
      if (isEdit) await api.patch(`/bandaki/customers/${customer.id}/`, payload);
      else await api.post("/bandaki/customers/", payload);
      onSaved();
    } catch (e) {
      setError(apiError(e));
    }
  };

  return (
    <Modal open onClose={onClose} title={isEdit ? "Edit customer" : "New bandaki customer"}>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {error && <ErrorState message={error} />}
        <Field label="Name" required>
          <input className="input" autoFocus {...register("name", { required: true })} />
        </Field>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Phone">
            <input className="input" {...register("phone")} />
          </Field>
          <Field label="Location">
            <input className="input" {...register("location")} />
          </Field>
        </div>
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
