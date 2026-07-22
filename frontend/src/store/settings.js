import { create } from "zustand";
import api from "../lib/api";

// Holds the shop's calendar preference (BS/AD). Loaded once after login and
// used by formatDate everywhere. Storage stays AD; this is display-only.
export const useSettingsStore = create((set) => ({
  calendar: "BS", // BS is the default; the shop can switch to AD in Settings
  loaded: false,

  load: async () => {
    try {
      const { data } = await api.get("/auth/settings/");
      set({ calendar: data.calendar_preference, loaded: true });
    } catch {
      set({ loaded: true });
    }
  },

  setCalendar: (calendar) => set({ calendar }),
}));
