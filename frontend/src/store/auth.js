import { create } from "zustand";
import { persist } from "zustand/middleware";

// Auth state is persisted to localStorage so a refresh keeps the session.
// Tokens are JWTs issued by the Django backend; `user` mirrors /auth/me.
export const useAuthStore = create(
  persist(
    (set) => ({
      access: null,
      refresh: null,
      user: null,

      setTokens: ({ access, refresh }) => set({ access, refresh }),
      setUser: (user) => set({ user }),

      login: ({ access, refresh, user }) => set({ access, refresh, user }),

      logout: () => set({ access: null, refresh: null, user: null }),
    }),
    {
      name: "karigar-auth",
      partialize: (s) => ({ access: s.access, refresh: s.refresh, user: s.user }),
    },
  ),
);

// Convenience selectors.
export const selectIsAuthenticated = (s) => Boolean(s.access);
export const selectRole = (s) => s.user?.role ?? null;
