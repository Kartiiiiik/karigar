import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Lock, AlertTriangle, LogOut, X } from "lucide-react";
import api from "../lib/api";
import { useAuthStore, selectIsAuthenticated } from "../store/auth";
import { useSubscriptionStore } from "../store/subscription";
import { useSettingsStore } from "../store/settings";
import { formatDate } from "../lib/date";

const POLL_MS = 60000; // re-check every 60s
const WARN_DAYS = 7; // show the pre-expiry banner within this many days

// Platform administrator contact shown on the lock screen.
const ADMIN_CONTACT = "Kartik Soni · +977 9824017387";

/**
 * Wraps the whole app. Polls the subscription status while authenticated and,
 * when the shop is expired, renders a non-dismissible full-screen lock over the
 * app. Also shows a subtle, dismissible pre-expiry banner in the final days.
 *
 * Backend enforcement is authoritative (see the subscription gate); this is the
 * UX layer that reflects it and enables instant lock + auto-recovery.
 */
export default function SubscriptionGate({ children }) {
  const isAuth = useAuthStore(selectIsAuthenticated);
  const active = useSubscriptionStore((s) => s.active);
  const loaded = useSubscriptionStore((s) => s.loaded);
  const setStatus = useSubscriptionStore((s) => s.setStatus);
  const reset = useSubscriptionStore((s) => s.reset);

  useEffect(() => {
    if (!isAuth) {
      reset();
      return;
    }
    let alive = true;
    const check = async () => {
      try {
        const { data } = await api.get("/subscription/status");
        if (alive) setStatus(data);
      } catch {
        // 403s are handled by the axios interceptor; ignore transient errors so
        // a blip never falsely unlocks the app.
      }
    };
    check();
    const id = window.setInterval(check, POLL_MS);
    const onFocus = () => check(); // re-check the instant the tab regains focus
    window.addEventListener("focus", onFocus);
    return () => {
      alive = false;
      window.clearInterval(id);
      window.removeEventListener("focus", onFocus);
    };
  }, [isAuth, setStatus, reset]);

  const locked = isAuth && loaded && active === false;
  const warning = isAuth && loaded && active === true;

  return (
    <>
      {children}
      {warning && <ExpiryBanner />}
      {locked && <SubscriptionLock />}
    </>
  );
}

// ---------------------------------------------------------------------------
// Non-dismissible full-screen lock
// ---------------------------------------------------------------------------
function SubscriptionLock() {
  const navigate = useNavigate();
  const logout = useAuthStore((s) => s.logout);
  const message = useSubscriptionStore((s) => s.message);
  const ref = useRef(null);

  useEffect(() => {
    // Block background scroll and trap focus inside the dialog. There is no
    // close path: no X, no ESC handler, no backdrop dismissal.
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const node = ref.current;
    node?.focus();

    const onKey = (e) => {
      if (e.key !== "Tab") return;
      const focusables = node.querySelectorAll(
        "button, [href], input, [tabindex]:not([tabindex='-1'])",
      );
      if (!focusables.length) {
        e.preventDefault();
        return;
      }
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey, true);
    return () => {
      document.body.style.overflow = prevOverflow;
      document.removeEventListener("keydown", onKey, true);
    };
  }, []);

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  return (
    <div
      ref={ref}
      tabIndex={-1}
      role="dialog"
      aria-modal="true"
      aria-labelledby="sub-lock-title"
      className="fixed inset-0 z-[100] flex items-center justify-center bg-gray-900/80 p-4 backdrop-blur-sm outline-none"
    >
      <div className="w-full max-w-md rounded-2xl bg-white p-7 text-center shadow-2xl">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-red-100">
          <Lock className="h-7 w-7 text-red-600" />
        </div>
        <h2 id="sub-lock-title" className="text-xl font-bold text-gray-900">
          Subscription ended
        </h2>
        <p className="mt-3 text-sm leading-relaxed text-gray-600">
          {message ||
            "Your subscription has ended. Please contact the administrator to continue the services."}
        </p>
        <p className="mt-4 rounded-lg bg-gray-50 px-4 py-3 text-xs text-gray-500">
          To restore access, please contact {ADMIN_CONTACT}. This screen will
          clear automatically once your subscription is renewed.
        </p>
        <button
          type="button"
          onClick={handleLogout}
          className="btn-secondary mt-6 inline-flex items-center gap-2"
        >
          <LogOut size={16} /> Log out
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Dismissible pre-expiry banner (final days only)
// ---------------------------------------------------------------------------
function ExpiryBanner() {
  const daysRemaining = useSubscriptionStore((s) => s.daysRemaining);
  const endDate = useSubscriptionStore((s) => s.endDate);
  const calendar = useSettingsStore((s) => s.calendar);
  const dateFormat = useSettingsStore((s) => s.dateFormat);
  const [dismissed, setDismissed] = useState(false);

  // Only warn for a real, dated subscription nearing expiry. Superusers report
  // {active:true, end_date:null, days_remaining:0}, which must NOT trigger the
  // banner.
  if (dismissed || !endDate || daysRemaining > WARN_DAYS || daysRemaining < 0) return null;

  const when =
    daysRemaining === 0
      ? "today"
      : `in ${daysRemaining} day${daysRemaining === 1 ? "" : "s"}`;
  const ends = endDate ? formatDate(endDate, calendar, { format: dateFormat }) : "";

  return (
    <div className="fixed bottom-4 right-4 z-50 flex max-w-sm items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 shadow-lg">
      <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
      <div className="min-w-0 flex-1 text-sm">
        <p className="font-semibold text-amber-900">Subscription expiring {when}</p>
        <p className="mt-0.5 text-amber-800">
          {ends ? `Ends ${ends}. ` : ""}Contact the administrator to renew and
          avoid interruption.
        </p>
      </div>
      <button
        type="button"
        aria-label="Dismiss"
        onClick={() => setDismissed(true)}
        className="shrink-0 rounded p-1 text-amber-500 hover:bg-amber-100 hover:text-amber-700"
      >
        <X size={16} />
      </button>
    </div>
  );
}
