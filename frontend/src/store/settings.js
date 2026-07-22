import { create } from "zustand";
import api from "../lib/api";

// Holds the shop's display preferences (calendar BS/AD + date format). Loaded
// once after login and used by formatDate everywhere. Storage stays AD; these
// are display-only.
export const useSettingsStore = create((set) => ({
  calendar: "BS", // BS is the default; the shop can switch to AD in Settings
  dateFormat: "DMY_TEXT",
  loaded: false,

  load: async () => {
    try {
      const { data } = await api.get("/auth/settings/");
      set({
        calendar: data.calendar_preference,
        dateFormat: data.date_format || "DMY_TEXT",
        loaded: true,
      });
    } catch {
      set({ loaded: true });
    }
  },

  setCalendar: (calendar) => set({ calendar }),
  setDateFormat: (dateFormat) => set({ dateFormat }),
}));
