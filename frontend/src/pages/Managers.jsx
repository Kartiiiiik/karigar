import { useState } from "react";
import { useForm } from "react-hook-form";
import { Plus, UserX, UserCheck } from "lucide-react";
import api, { apiError } from "../lib/api";
import { useFetch } from "../hooks/useFetch";
import { PageHeader, Spinner, EmptyState, ErrorState, Modal, Field, Badge, STICKY_TH } from "../components/ui";

export default function Managers() {
  const { data, loading, error, refresh } = useFetch("/auth/managers/", { page_size: 200 });
  const [adding, setAdding] = useState(false);
  const items = data?.results ?? [];

  const toggle = async (m) => {
    const action = m.is_active ? "deactivate" : "activate";
    try {
      await api.post(`/auth/managers/${m.id}/${action}/`);
      refresh();
    } catch (e) {
      alert(apiError(e));
    }
  };

  const bodyTd = "whitespace-nowrap border-b border-gray-100 px-3 py-2.5";

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Managers"
        subtitle="Manager accounts can run the shop but cannot manage other managers."
        actions={
          <button className="btn-primary" onClick={() => setAdding(true)}>
            <Plus size={16} /> Add manager
          </button>
        }
      />

      {error && <ErrorState message={error} />}
      {loading ? (
        <Spinner />
      ) : items.length === 0 ? (
        <EmptyState message="No managers yet." />
      ) : (
        <div className="min-h-0 flex-1 overflow-auto rounded-xl border border-gray-200 bg-white">
          <table className="min-w-full border-separate border-spacing-0 text-sm">
            <thead className="text-left text-xs uppercase text-gray-500">
              <tr>
                <th className={STICKY_TH}>Name</th>
                <th className={STICKY_TH}>Username</th>
                <th className={STICKY_TH}>Email</th>
                <th className={STICKY_TH}>Status</th>
                <th className={STICKY_TH}></th>
              </tr>
            </thead>
            <tbody>
              {items.map((m) => (
                <tr key={m.id} className="hover:bg-gray-50">
                  <td className={`${bodyTd} font-medium text-gray-900`}>{m.full_name || m.username}</td>
                  <td className={`${bodyTd} text-gray-600`}>@{m.username}</td>
                  <td className={`${bodyTd} text-gray-600`}>{m.email || "—"}</td>
                  <td className={bodyTd}>
                    {m.is_active ? <Badge tone="green">Active</Badge> : <Badge tone="red">Inactive</Badge>}
                  </td>
                  <td className={`${bodyTd} text-right`}>
                    <button className="btn-secondary py-1" onClick={() => toggle(m)}>
                      {m.is_active ? <><UserX size={15} /> Deactivate</> : <><UserCheck size={15} /> Activate</>}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {adding && <ManagerForm onClose={() => setAdding(false)} onSaved={() => { setAdding(false); refresh(); }} />}
    </div>
  );
}

function ManagerForm({ onClose, onSaved }) {
  const { register, handleSubmit } = useForm();
  const [error, setError] = useState("");

  const onSubmit = async (v) => {
    setError("");
    try {
      await api.post("/auth/managers/", v);
      onSaved();
    } catch (e) {
      setError(apiError(e));
    }
  };

  return (
    <Modal open onClose={onClose} title="Add manager">
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {error && <ErrorState message={error} />}
        <Field label="Username" required>
          <input className="input" {...register("username", { required: true })} />
        </Field>
        <Field label="Full name">
          <input className="input" {...register("full_name")} />
        </Field>
        <Field label="Email">
          <input className="input" type="email" {...register("email")} />
        </Field>
        <Field label="Password" required>
          <input className="input" type="password" {...register("password", { required: true })} />
        </Field>
        <div className="flex justify-end gap-2">
          <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary">Create</button>
        </div>
      </form>
    </Modal>
  );
}
