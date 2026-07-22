import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useForm, useWatch } from "react-hook-form";
import { Plus, Pencil, KeyRound, UserX, UserCheck, Phone, MapPin, Copy, RefreshCw } from "lucide-react";
import api, { apiError } from "../lib/api";
import { useFetch } from "../hooks/useFetch";
import { PageHeader, Spinner, EmptyState, ErrorState, Modal, Field, DrCrBadge, Badge } from "../components/ui";
import DateInput from "../components/DateInput";
import { useSettingsStore } from "../store/settings";
import { formatGoldBalance, formatCashBalance } from "../lib/format";

// Decompose a signed opening balance into {amount, direction} for the form.
function decompose(signed) {
  const n = Number(signed ?? 0);
  return { amount: Math.abs(n), direction: n < 0 ? "cr" : "dr" };
}
// Recompose amount + direction into a signed value string.
function recompose(amount, direction) {
  const a = Math.abs(Number(amount || 0));
  return direction === "cr" ? -a : a;
}

export default function Karigars() {
  const { data, loading, error, refresh } = useFetch("/karigars/", { page_size: 200 });
  const [editing, setEditing] = useState(null);
  const items = data?.results ?? [];

  // Open the add form when arrived via the dashboard quick action.
  const [sp, setSp] = useSearchParams();
  useEffect(() => {
    if (sp.get("action") === "new") {
      setEditing({});
      sp.delete("action");
      setSp(sp, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div>
      <PageHeader
        title="Karigars"
        subtitle="Goldsmiths and their current gold & cash balances."
        actions={
          <button className="btn-primary" onClick={() => setEditing({})}>
            <Plus size={16} /> Add karigar
          </button>
        }
      />

      {error && <ErrorState message={error} />}
      {loading ? (
        <Spinner />
      ) : items.length === 0 ? (
        <EmptyState message="No karigars yet." />
      ) : (
        <>
          {/* Desktop table */}
          <div className="hidden overflow-x-auto rounded-xl border border-gray-200 bg-white lg:block">
            <table className="min-w-full divide-y divide-gray-200 whitespace-nowrap text-sm">
              <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
                <tr>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Username</th>
                  <th className="px-4 py-3">Password</th>
                  <th className="px-4 py-3">Contact</th>
                  <th className="px-4 py-3">Gold balance</th>
                  <th className="px-4 py-3">Cash balance</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {items.map((k) => (
                  <tr key={k.id}>
                    <td className="px-4 py-3">
                      <p className="font-medium text-gray-900">{k.full_name}</p>
                    </td>
                    <td className="px-4 py-3"><CopyText value={k.username} /></td>
                    <td className="px-4 py-3"><CopyText value={k.password} mono /></td>
                    <td className="px-4 py-3 text-gray-600">
                      {k.phone || "—"}
                      {k.location && <p className="text-xs text-gray-400">{k.location}</p>}
                    </td>
                    <td className="px-4 py-3"><DrCrBadge label={formatGoldBalance(k.gold_balance)} /></td>
                    <td className="px-4 py-3"><DrCrBadge label={formatCashBalance(k.cash_balance)} /></td>
                    <td className="px-4 py-3">
                      {k.is_active ? <Badge tone="green">Active</Badge> : <Badge tone="red">Inactive</Badge>}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button className="text-gray-400 hover:text-brand-600" onClick={() => setEditing(k)}>
                        <Pencil size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <div className="space-y-3 lg:hidden">
            {items.map((k) => (
              <div key={k.id} className="card">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-medium text-gray-900">{k.full_name}</p>
                    <p className="text-xs text-gray-400">@{k.username}</p>
                  </div>
                  <button className="text-gray-400 hover:text-brand-600" onClick={() => setEditing(k)}>
                    <Pencil size={16} />
                  </button>
                </div>
                <div className="mt-2 space-y-1 text-sm text-gray-600">
                  <p className="flex items-center gap-2"><span className="w-16 text-xs text-gray-400">User</span> <CopyText value={k.username} /></p>
                  <p className="flex items-center gap-2"><span className="w-16 text-xs text-gray-400">Pass</span> <CopyText value={k.password} mono /></p>
                  {k.phone && <p className="flex items-center gap-1"><Phone size={13} /> {k.phone}</p>}
                  {k.location && <p className="flex items-center gap-1"><MapPin size={13} /> {k.location}</p>}
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <DrCrBadge label={formatGoldBalance(k.gold_balance)} />
                  <DrCrBadge label={formatCashBalance(k.cash_balance)} />
                  {!k.is_active && <Badge tone="red">Inactive</Badge>}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {editing && (
        <KarigarForm
          karigar={editing}
          onClose={() => setEditing(null)}
          onRefresh={refresh}
          onSaved={() => { setEditing(null); refresh(); }}
        />
      )}
    </div>
  );
}

function KarigarForm({ karigar, onClose, onRefresh, onSaved }) {
  const isEdit = Boolean(karigar.id);
  const g = decompose(karigar.opening_gold_g);
  const c = decompose(karigar.opening_cash_npr);
  const calendar = useSettingsStore((s) => s.calendar);
  const { register, handleSubmit, control, setValue } = useForm({
    defaultValues: {
      full_name: karigar.full_name ?? "",
      phone: karigar.phone ?? "",
      location: karigar.location ?? "",
      joined_date: karigar.joined_date ?? "",
      opening_gold_amount: g.amount,
      opening_gold_dir: g.direction,
      opening_cash_amount: c.amount,
      opening_cash_dir: c.direction,
      is_active: karigar.is_active ?? true,
    },
  });
  const joinedDate = useWatch({ control, name: "joined_date" });
  const [photo, setPhoto] = useState(null);
  const [error, setError] = useState("");
  const [pwOpen, setPwOpen] = useState(false);
  const [created, setCreated] = useState(null); // {username, generated_password}

  const onSubmit = async (v) => {
    setError("");
    const openingGold = recompose(v.opening_gold_amount, v.opening_gold_dir);
    const openingCash = recompose(v.opening_cash_amount, v.opening_cash_dir);
    try {
      if (isEdit) {
        // Edits are JSON PATCH; the photo (if any) goes to a dedicated endpoint.
        const payload = {
          full_name: v.full_name,
          phone: v.phone || "",
          location: v.location || "",
          opening_gold_g: openingGold,
          opening_cash_npr: openingCash,
          is_active: v.is_active,
        };
        if (v.joined_date) payload.joined_date = v.joined_date;
        await api.patch(`/karigars/${karigar.id}/`, payload);
        if (photo) {
          const pf = new FormData();
          pf.append("photo", photo);
          await api.post(`/karigars/${karigar.id}/photo/`, pf);
        }
      } else {
        // Create is multipart (may include the photo). Username + password are
        // auto-generated by the backend; the response returns them so we can
        // show the manager the credentials to share.
        const fd = new FormData();
        fd.append("full_name", v.full_name);
        fd.append("phone", v.phone || "");
        fd.append("location", v.location || "");
        if (v.joined_date) fd.append("joined_date", v.joined_date);
        fd.append("opening_gold_g", openingGold);
        fd.append("opening_cash_npr", openingCash);
        if (photo) fd.append("photo", photo);
        const { data } = await api.post("/karigars/", fd);
        // Show credentials first; refresh the list behind the modal.
        setCreated({ username: data.username, password: data.generated_password });
        onRefresh();
        return;
      }
      onSaved();
    } catch (e) {
      setError(apiError(e));
    }
  };

  const toggleActive = async () => {
    try {
      if (karigar.is_active) await api.delete(`/karigars/${karigar.id}/`);
      else await api.post(`/karigars/${karigar.id}/activate/`);
      onSaved();
    } catch (e) {
      setError(apiError(e));
    }
  };

  // After creation, show the generated login credentials for the manager to share.
  if (created) {
    return (
      <Modal open onClose={onSaved} title="Karigar created">
        <Credentials username={created.username} password={created.password} />
        <div className="mt-4 flex justify-end">
          <button className="btn-primary" onClick={onSaved}>Done</button>
        </div>
      </Modal>
    );
  }

  return (
    <Modal open onClose={onClose} title={isEdit ? `Edit ${karigar.full_name}` : "Add karigar"} wide>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {error && <ErrorState message={error} />}

        {!isEdit && (
          <p className="rounded-lg bg-brand-50 px-3 py-2 text-sm text-brand-700">
            A login username and password will be generated automatically and
            shown to you after saving, so you can share them with the karigar.
          </p>
        )}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Full name" required>
            <input className="input" {...register("full_name", { required: true })} />
          </Field>
          <Field label="Phone">
            <input className="input" {...register("phone")} />
          </Field>
        </div>

        <Field label="Location / address">
          <input className="input" {...register("location")} />
        </Field>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Opening gold (g)">
            <div className="flex gap-2">
              <input className="input" type="number" step="0.001" min="0" {...register("opening_gold_amount")} />
              <select className="input w-24" {...register("opening_gold_dir")}>
                <option value="dr">Dr</option>
                <option value="cr">Cr</option>
              </select>
            </div>
          </Field>
          <Field label="Opening cash (NPR)">
            <div className="flex gap-2">
              <input className="input" type="number" step="0.01" min="0" {...register("opening_cash_amount")} />
              <select className="input w-24" {...register("opening_cash_dir")}>
                <option value="dr">Dr</option>
                <option value="cr">Cr</option>
              </select>
            </div>
          </Field>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label={`Joined date (${calendar})`}>
            <DateInput calendar={calendar} value={joinedDate}
              onChange={(v) => setValue("joined_date", v)} />
          </Field>
          <Field label="Photo">
            <input
              className="input"
              type="file"
              accept="image/*"
              capture="environment"
              onChange={(e) => setPhoto(e.target.files?.[0] ?? null)}
            />
          </Field>
        </div>

        {isEdit && karigar.photo && (
          <img src={karigar.photo} alt="" className="h-20 w-20 rounded-lg object-cover" />
        )}

        <div className="flex flex-wrap items-center justify-between gap-2 pt-2">
          <div className="flex gap-2">
            {isEdit && (
              <>
                <button type="button" className="btn-secondary" onClick={() => setPwOpen(true)}>
                  <KeyRound size={15} /> Reset password
                </button>
                <button type="button" className="btn-secondary" onClick={toggleActive}>
                  {karigar.is_active ? <><UserX size={15} /> Deactivate</> : <><UserCheck size={15} /> Activate</>}
                </button>
              </>
            )}
          </div>
          <div className="flex gap-2">
            <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-primary">Save</button>
          </div>
        </div>
      </form>

      {pwOpen && (
        <ResetPassword karigar={karigar} onClose={() => setPwOpen(false)} />
      )}
    </Modal>
  );
}

// Inline value with a copy-to-clipboard button (used for username/password).
function CopyText({ value, mono }) {
  if (!value) return <span className="text-gray-400">—</span>;
  return (
    <span className="inline-flex items-center gap-1">
      <span className={mono ? "font-mono" : ""}>{value}</span>
      <button
        type="button"
        className="text-gray-400 hover:text-brand-600"
        title="Copy"
        onClick={() => navigator.clipboard?.writeText(value)}
      >
        <Copy size={13} />
      </button>
    </span>
  );
}

// A readable random password (letters + digits), generated client-side.
function genPassword() {
  const chars = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  let out = "";
  const arr = new Uint32Array(10);
  crypto.getRandomValues(arr);
  for (let i = 0; i < 10; i++) out += chars[arr[i] % chars.length];
  return out;
}

// Shows login credentials in plain text with copy buttons so the manager can
// pass them to the karigar (passwords are intentionally NOT masked here).
function Credentials({ username, password }) {
  const copy = (text) => navigator.clipboard?.writeText(text);
  const Row = ({ label, value }) => (
    <div>
      <p className="label">{label}</p>
      <div className="flex items-center gap-2">
        <code className="flex-1 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 font-mono text-sm">{value}</code>
        <button type="button" className="btn-secondary" onClick={() => copy(value)}>
          <Copy size={15} /> Copy
        </button>
      </div>
    </div>
  );
  return (
    <div className="space-y-3">
      <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
        Share these with the karigar. The password is shown only now — it cannot
        be retrieved later, but you can reset it anytime.
      </p>
      <Row label="Username" value={username} />
      <Row label="Password" value={password} />
    </div>
  );
}

function ResetPassword({ karigar, onClose }) {
  const { register, handleSubmit, setValue, watch } = useForm({
    defaultValues: { new_password: genPassword() },
  });
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const pw = watch("new_password");

  const onSubmit = async (v) => {
    setError("");
    try {
      await api.post(`/karigars/${karigar.id}/set_password/`, { new_password: v.new_password });
      setDone(true);
    } catch (e) {
      setError(apiError(e));
    }
  };

  return (
    <Modal open onClose={onClose} title="Reset password">
      {done ? (
        <div className="space-y-4">
          <p className="text-sm text-green-700">Password updated. Share it with the karigar:</p>
          <Credentials username={karigar.username} password={pw} />
          <div className="flex justify-end">
            <button className="btn-primary" onClick={onClose}>Done</button>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          {error && <ErrorState message={error} />}
          <Field label="New password (visible)" required>
            <div className="flex gap-2">
              {/* text, not password — the manager needs to read & share it */}
              <input className="input font-mono" type="text" {...register("new_password", { required: true })} />
              <button type="button" className="btn-secondary" onClick={() => setValue("new_password", genPassword())}>
                <RefreshCw size={15} /> Generate
              </button>
            </div>
          </Field>
          <div className="flex justify-end gap-2">
            <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-primary">Update</button>
          </div>
        </form>
      )}
    </Modal>
  );
}
