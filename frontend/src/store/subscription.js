import { create } from "zustand";

// Subscription status for the current shop, driven by /subscription/status
// polling and by the axios 403 interceptor. `active` is null until the first
// check completes, then a boolean. When it becomes false the app is locked by
// <SubscriptionGate>; when it flips back to true (admin extended it) the lock
// clears automatically.
export const useSubscriptionStore = create((set) => ({
  active: null,
  endDate: null,
  daysRemaining: 0,
  message: "",
  loaded: false,

  setStatus: ({ active, end_date, days_remaining, message }) =>
    set({
      active,
      endDate: end_date ?? null,
      daysRemaining: days_remaining ?? 0,
      message: message ?? "",
      loaded: true,
    }),

  // Called by the axios interceptor on any 403 SUBSCRIPTION_EXPIRED so a
  // mid-session expiry locks the app instantly, without waiting for the poll.
  markExpired: (message) =>
    set((s) => ({ active: false, loaded: true, message: message || s.message })),

  reset: () =>
    set({ active: null, endDate: null, daysRemaining: 0, message: "", loaded: false }),
}));
