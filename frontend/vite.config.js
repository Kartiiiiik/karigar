import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The frontend talks to the Django API. In dev we proxy /api to the backend
// so the browser sees a single origin and CORS stays simple.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY || "http://localhost:8000",
        changeOrigin: true,
      },
      "/media": {
        target: process.env.VITE_API_PROXY || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
