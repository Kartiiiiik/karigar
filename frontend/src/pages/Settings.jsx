import { useState } from "react";
import { useForm } from "react-hook-form";
import { Calendar, Check, CalendarClock } from "lucide-react";
import api, { apiError } from "../lib/api";
import { PageHeader, ErrorState, Field } from "../components/ui";
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

      <div className="card space-y-3">
        <h2 className="flex items-center gap-2 font-semibold text-gray-900">
          <Calendar size={18} /> Calendar
        </h2>
        <p className="text-sm text-gray-500">
          Controls how dates are displayed across the app and in reports. Data is
          always stored in AD (Gregorian); this only changes the display.
        </p>
        {calError && <ErrorState message={calError} />}
        <div className="flex gap-2">
          {["BS", "AD"].map((c) => (
            <button
              key={c}
              disabled={saving}
              onClick={() => changeCalendar(c)}
              className={`flex-1 rounded-lg border px-4 py-3 text-sm font-medium ${
                calendar === c ? "border-brand-500 bg-brand-50 text-brand-700" : "border-gray-300 text-gray-600"
              }`}
            >
              {calendar === c && <Check size={14} className="mr-1 inline" />}
              {c === "BS" ? "Bikram Sambat (BS)" : "Gregorian (AD)"}
            </button>
          ))}
        </div>
        {savedCal && <p className="text-xs text-green-600">Calendar saved.</p>}
      </div>

      <div className="card space-y-3">
        <h2 className="flex items-center gap-2 font-semibold text-gray-900">
          <CalendarClock size={18} /> Date format
        </h2>
        <p className="text-sm text-gray-500">
          How dates are written wherever they appear ({calendar} calendar).
        </p>
        <Field label="Format">
          <select
            className="input"
            value={dateFormat}
            disabled={saving}
            onChange={(e) => changeDateFormat(e.target.value)}
          >
            {DATE_FORMATS.map((f) => (
              <option key={f.value} value={f.value}>{f.label}</option>
            ))}
          </select>
        </Field>
        <p className="text-xs text-gray-400">
          Today shows as:{" "}
          <span className="font-medium text-gray-600">
            {formatDate(today, calendar, { format: dateFormat })}
          </span>
          {savedFmt && <span className="ml-2 text-green-600">Saved</span>}
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
