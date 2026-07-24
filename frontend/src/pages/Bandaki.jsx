import { useMemo, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { Plus, Pencil, UserPlus } from "lucide-react";
import api, { apiError } from "../lib/api";
import { useFetch } from "../hooks/useFetch";
import {
  PageHeader, Spinner, EmptyState, ErrorState, Modal, Field, Badge, SortableTh, STICKY_TH,
} from "../components/ui";
import DateInput from "../components/DateInput";
import { formatAmount } from "../lib/format";
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
  const [loan, setLoan] = useState(null);
  const customers = custData?.results ?? [];
  const items = data?.results ?? [];
  const count = data?.count ?? 0;

  const sort = (field) => setOrdering((o) => (o === field ? `-${field}` : field));

  // Footer totals across the loaded rows (all rows fetched in one page).
  const totals = items.reduce(
    (acc, l) => {
      acc.principal += Number(l.gross_amount);
      acc.interest += Number(l.interest_amount);
      acc.total += Number(l.total_amount);
      return acc;
    },
    { principal: 0, interest: 0, total: 0 },
  );

  // Sticky-cell classes + total-row cells (cols: Date, Customer, Principal,
  // Rate, Days, Interest, Total, Remarks, action).
  const bodyTd = "whitespace-nowrap border-b border-gray-100 px-3 py-2.5";
  const footTd = "sticky bottom-0 z-20 h-10 whitespace-nowrap border-t border-amber-200 bg-amber-50 px-3 font-semibold text-gray-800";
  const totalCells = [
    `Total (${count})`, "", formatAmount(totals.principal), "", "",
    formatAmount(totals.interest), formatAmount(totals.total), "", "",
  ];

  return (
    <div className="flex h-full flex-col">
      <div className="mb-3 shrink-0 space-y-2">
        <div className="flex gap-2">
          <button className="btn-primary flex-1 sm:flex-none" onClick={() => setLoan({})}>
            <Plus size={16} /> New bandaki
          </button>
        </div>
        <div className="flex flex-wrap gap-2 sm:justify-end">
          <select
            className="input min-w-0 flex-1 truncate sm:w-48 sm:flex-none"
            value={filters.customer}
            onChange={(e) => setFilters((f) => ({ ...f, customer: e.target.value }))}
          >
            <option value="">All customers</option>
            {customers.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <select
            className="input w-28 shrink-0 sm:w-36"
            value={filters.is_active}
            onChange={(e) => setFilters((f) => ({ ...f, is_active: e.target.value }))}
          >
            <option value="">All</option>
            <option value="true">Active</option>
            <option value="false">Closed</option>
          </select>
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
                <SortableTh label={<>Principal{NPR}</>} field="gross_amount" ordering={ordering} onSort={sort} />
                <SortableTh label="Rate" field="interest_rate" ordering={ordering} onSort={sort} />
                <th className={STICKY_TH}>Days</th>
                <th className={STICKY_TH}>Interest{NPR}</th>
                <th className={STICKY_TH}>Total{NPR}</th>
                <th className={STICKY_TH}>Remarks</th>
                <th className={STICKY_TH}></th>
              </tr>
            </thead>
            <tbody>
              {items.map((l) => (
                <tr key={l.id} className={`hover:bg-gray-50 ${l.is_active ? "" : "opacity-60"}`}>
                  <td className={`${bodyTd} text-gray-600`}>{formatDate(l.loan_date, calendar, { format: dateFormat })}</td>
                  <td className={bodyTd}>
                    <span className="inline-flex items-center gap-2">
                      {l.customer_name}
                      {!l.is_active && <Badge tone="gray">Closed</Badge>}
                    </span>
                  </td>
                  <td className={`${bodyTd} font-medium`}>{formatAmount(l.gross_amount)}</td>
                  <td className={`${bodyTd} text-gray-600`}>
                    {Number(l.interest_rate)}% <span className="text-gray-400">/{PERIOD_SHORT[l.interest_period]}</span>
                  </td>
                  <td className={`${bodyTd} text-gray-500`}>{l.days_elapsed}</td>
                  <td className={`${bodyTd} font-medium text-dr`}>{formatAmount(l.interest_amount)}</td>
                  <td className={`${bodyTd} font-semibold`}>{formatAmount(l.total_amount)}</td>
                  <td className={`${bodyTd} text-gray-500`}>{l.remarks || "—"}</td>
                  <td className={`${bodyTd} text-right`}>
                    <button className="text-gray-400 hover:text-brand-600" onClick={() => setLoan(l)}>
                      <Pencil size={15} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>{totalCells.map((c, i) => <td key={i} className={footTd}>{c}</td>)}</tr>
            </tfoot>
          </table>
        </div>
      )}

      {loan && (
        <LoanForm
          loan={loan}
          customers={customers}
          refreshCustomers={refreshCustomers}
          onClose={() => setLoan(null)}
          onSaved={() => { setLoan(null); refresh(); }}
        />
      )}
    </div>
  );
}

function LoanForm({ loan, customers, refreshCustomers, onClose, onSaved }) {
  const isEdit = Boolean(loan.id);
  const calendar = useSettingsStore((s) => s.calendar);
  const { register, handleSubmit, control, setValue } = useForm({
    defaultValues: {
      customer: loan.customer ?? "",
      gross_amount: loan.gross_amount ?? "",
      interest_rate: loan.interest_rate ?? "",
      interest_period: loan.interest_period ?? "monthly",
      remarks: loan.remarks ?? "",
      loan_date: loan.loan_date ?? new Date().toISOString().slice(0, 10),
      is_active: loan.is_active ?? true,
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
            <select className="input" {...register("customer", { required: true })}>
              <option value="">Select customer…</option>
              {customers.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
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
            <select className="input" {...register("interest_period", { required: true })}>
              <option value="monthly">Monthly</option>
              <option value="yearly">Yearly</option>
            </select>
          </Field>
        </div>

        <Field label="Remarks">
          <textarea className="input" rows={2} {...register("remarks")} />
        </Field>

        {isEdit && (
          <Field label="Loan status">
            <select className="input" {...register("is_active")}>
              <option value={true}>Active (still owed)</option>
              <option value={false}>Closed (repaid)</option>
            </select>
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
