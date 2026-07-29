import { useState } from "react";
import { useForm } from "react-hook-form";
import { Calendar, Check } from "lucide-react";
import api, { apiError } from "../lib/api";
import { PageHeader, ErrorState, Field } from "../components/ui";
import Select from "../components/Select";
import { useSettingsStore } from "../store/settings";
import { formatDate, DATE_FORMATS } from "../lib/date";

export default function Settings() {
  const { calendar, setCalendar, dateFormat, setDateFormat } = useSettingsStore();
  const [saving, setSaving] = useState(false);
  const [savedCal, setSavedCal] = useState(false);
  const [savedFmt, setSavedFmt] = useState(false);
  const [calError, setCalError] = useState("");

  const patchSettings = async (payload, onOk) => {
    setSaving(true);
    setCalError("");
    try {
      await api.patch("/auth/settings/", payload);
      onOk();
    } catch (e) {
      setCalError(apiError(e));
    } finally {
      setSaving(false);
    }
  };

  const changeCalendar = (value) =>
    patchSettings({ calendar_preference: value }, () => {
      setCalendar(value);
      setSavedCal(true);
      setSavedFmt(false);
    });

  const changeDateFormat = (value) =>
    patchSettings({ date_format: value }, () => {
      setDateFormat(value);
      setSavedFmt(true);
      setSavedCal(false);
    });

  const today = new Date().toISOString();

  return (
    <div className="max-w-2xl space-y-6">
      <PageHeader title="Settings" subtitle="Shop-wide preferences." />

      {/* Display: calendar + date format in one card */}
      <div className="card space-y-4">
        <h2 className="flex items-center gap-2 font-semibold text-gray-900">
          <Calendar size={18} /> Display
        </h2>
        {calError && <ErrorState message={calError} />}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <p className="label">Calendar {savedCal && <span className="text-green-600">· saved</span>}</p>
            <div className="flex gap-2">
              {["BS", "AD"].map((c) => (
                <button
                  key={c}
                  disabled={saving}
                  onClick={() => changeCalendar(c)}
                  className={`flex-1 rounded-lg border px-3 py-2 text-sm font-medium ${
                    calendar === c ? "border-brand-500 bg-brand-50 text-brand-700" : "border-gray-300 text-gray-600"
                  }`}
                >
                  {calendar === c && <Check size={14} className="mr-1 inline" />}
                  {c}
                </button>
              ))}
            </div>
          </div>

          <div>
            <p className="label">Date format {savedFmt && <span className="text-green-600">· saved</span>}</p>
            <Select
              aria-label="Date format"
              value={dateFormat}
              disabled={saving}
              onChange={(v) => changeDateFormat(v)}
              options={DATE_FORMATS.map((f) => ({ value: f.value, label: f.label }))}
            />
          </div>
        </div>

        <p className="text-xs text-gray-400">
          Dates are stored in AD; this only changes the display. Today shows as{" "}
          <span className="font-medium text-gray-600">{formatDate(today, calendar, { format: dateFormat })}</span>.
        </p>
      </div>

      <ChangePassword />
    </div>
  );
}

function ChangePassword() {
  const { register, handleSubmit, reset } = useForm();
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  const onSubmit = async (v) => {
    setMsg("");
    setError("");
    try {
      await api.post("/auth/change-password/", v);
      setMsg("Password updated.");
      reset();
    } catch (e) {
      setError(apiError(e));
    }
  };

  return (
    <div className="card space-y-3">
      <h2 className="font-semibold text-gray-900">Change your password</h2>
      {error && <ErrorState message={error} />}
      {msg && <p className="text-sm text-green-600">{msg}</p>}
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
        <Field label="Current password" required>
          <input className="input" type="password" {...register("old_password", { required: true })} />
        </Field>
        <Field label="New password" required>
          <input className="input" type="password" {...register("new_password", { required: true })} />
        </Field>
        <div className="flex justify-end">
          <button className="btn-primary" type="submit">Update password</button>
        </div>
      </form>
    </div>
  );
}
