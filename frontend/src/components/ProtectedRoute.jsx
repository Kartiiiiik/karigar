import { Navigate, useLocation } from "react-router-dom";
import { useAuthStore } from "../store/auth";

/**
 * Guards routes. Redirects unauthenticated users to /login and, when
 * `roles` is provided, blocks users whose role is not in the list.
 *
 * This is a UX guard only — the API independently enforces every permission.
 */
export default function ProtectedRoute({ roles, children }) {
  const location = useLocation();
  const { access, user } = useAuthStore();

  if (!access) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (roles && user && !roles.includes(user.role)) {
    return <Navigate to="/" replace />;
  }

  return children;
}
