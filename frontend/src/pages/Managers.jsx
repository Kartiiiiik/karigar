import { useState } from "react";
import { useForm } from "react-hook-form";
import { Plus, UserX, UserCheck } from "lucide-react";
import api, { apiError } from "../lib/api";
import { useFetch } from "../hooks/useFetch";
import { PageHeader, Spinner, EmptyState, ErrorState, Modal, Field, Badge } from "../components/ui";

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

  return (
    <div>
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
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {items.map((m) => (
            <div key={m.id} className="card flex items-center justify-between">
              <div>
                <p className="font-medium text-gray-900">{m.full_name || m.username}</p>
                <p className="text-xs text-gray-400">@{m.username}{m.email ? ` · ${m.email}` : ""}</p>
                <div className="mt-2">
                  {m.is_active ? <Badge tone="green">Active</Badge> : <Badge tone="red">Inactive</Badge>}
                </div>
              </div>
              <button className="btn-secondary" onClick={() => toggle(m)}>
                {m.is_active ? <><UserX size={15} /> Deactivate</> : <><UserCheck size={15} /> Activate</>}
              </button>
            </div>
          ))}
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
