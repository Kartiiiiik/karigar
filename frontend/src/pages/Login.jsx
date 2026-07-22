import { useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate, useLocation } from "react-router-dom";
import { Gem, Loader2 } from "lucide-react";
import api, { apiError } from "../lib/api";
import { useAuthStore } from "../store/auth";

export default function Login() {
  const { register, handleSubmit, formState: { errors } } = useForm();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const login = useAuthStore((s) => s.login);
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || "/";

  const onSubmit = async (values) => {
    setError("");
    setLoading(true);
    try {
      const { data } = await api.post("/auth/login/", values);
      login({ access: data.access, refresh: data.refresh, user: data.user });
      navigate(from, { replace: true });
    } catch (e) {
      setError(apiError(e, "Invalid username or password."));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-brand-600 text-white">
            <Gem size={24} />
          </div>
          <h1 className="text-xl font-bold text-gray-900">Karigar</h1>
          <p className="text-sm text-gray-500">Jewellery Accounts Management</p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="card space-y-4">
          {error && (
            <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          <div>
            <label className="label" htmlFor="username">Username</label>
            <input
              id="username"
              className="input"
              autoComplete="username"
              {...register("username", { required: "Username is required" })}
            />
            {errors.username && (
              <p className="mt-1 text-xs text-red-600">{errors.username.message}</p>
            )}
          </div>

          <div>
            <label className="label" htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              className="input"
              autoComplete="current-password"
              {...register("password", { required: "Password is required" })}
            />
            {errors.password && (
              <p className="mt-1 text-xs text-red-600">{errors.password.message}</p>
            )}
          </div>

          <button type="submit" className="btn-primary w-full" disabled={loading}>
            {loading && <Loader2 size={16} className="animate-spin" />}
            Log in
          </button>
        </form>

        <p className="mt-4 text-center text-xs text-gray-400">
          Demo: owner / manager / karigar1 &middot; password Karigar@123
        </p>
      </div>
    </div>
  );
}
