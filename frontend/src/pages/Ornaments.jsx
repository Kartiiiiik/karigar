import { useState } from "react";
import { useForm } from "react-hook-form";
import { Plus, Pencil } from "lucide-react";
import api, { apiError } from "../lib/api";
import { useFetch } from "../hooks/useFetch";
import { PageHeader, Spinner, EmptyState, ErrorState, Modal, Field, Badge } from "../components/ui";

export default function Ornaments() {
  const { data, loading, error, refresh } = useFetch("/ornaments/", { page_size: 200 });
  const [editing, setEditing] = useState(null); // null = closed, {} = new, {..} = edit
  const items = data?.results ?? [];

  return (
    <div>
      <PageHeader
        title="Ornaments"
        subtitle="Types used when receiving finished pieces."
        actions={
          <button className="btn-primary" onClick={() => setEditing({})}>
            <Plus size={16} /> Add ornament
          </button>
        }
      />

      {error && <ErrorState message={error} />}
      {loading ? (
        <Spinner />
      ) : items.length === 0 ? (
        <EmptyState message="No ornament types yet." />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((o) => (
            <div key={o.id} className="card flex items-start justify-between">
              <div>
                <p className="font-medium text-gray-900">{o.name}</p>
                {o.description && <p className="text-sm text-gray-500">{o.description}</p>}
                <div className="mt-2">
                  {o.is_active ? <Badge tone="green">Active</Badge> : <Badge tone="red">Inactive</Badge>}
                </div>
              </div>
              <button className="text-gray-400 hover:text-brand-600" onClick={() => setEditing(o)}>
                <Pencil size={16} />
              </button>
            </div>
          ))}
        </div>
      )}

      {editing && (
        <OrnamentForm
          ornament={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            refresh();
          }}
        />
      )}
    </div>
  );
}

function OrnamentForm({ ornament, onClose, onSaved }) {
  const isEdit = Boolean(ornament.id);
  const { register, handleSubmit } = useForm({
    defaultValues: {
      name: ornament.name ?? "",
      description: ornament.description ?? "",
      is_active: ornament.is_active ?? true,
    },
  });
  const [error, setError] = useState("");

  const onSubmit = async (values) => {
    setError("");
    try {
      if (isEdit) await api.patch(`/ornaments/${ornament.id}/`, values);
      else await api.post("/ornaments/", values);
      onSaved();
    } catch (e) {
      setError(apiError(e));
    }
  };

  return (
    <Modal open onClose={onClose} title={isEdit ? "Edit ornament" : "Add ornament"}>
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        {error && <ErrorState message={error} />}
        <Field label="Name" required>
          <input className="input" {...register("name", { required: true })} />
        </Field>
        <Field label="Description">
          <textarea className="input" rows={2} {...register("description")} />
        </Field>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" {...register("is_active")} /> Active
        </label>
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn-primary">Save</button>
        </div>
      </form>
    </Modal>
  );
}
