import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The frontend talks to the Django API. In dev we proxy /api to the backend
// so the browser sees a single origin and CORS stays simple.
//
// The default target is the nginx container (published as 8080:80), which
// forwards /api and /media on to backend:8000. Going through nginx rather than
// straight to Django is deliberate: docker-compose.yml never publishes the
// backend's port, so localhost:8000 is unreachable from the host. Set
// VITE_API_PROXY to override — e.g. http://localhost:8000 when running
// `manage.py runserver` outside Docker.
const API_PROXY = process.env.VITE_API_PROXY || "http://localhost:8080";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: API_PROXY,
        changeOrigin: true,
      },
      "/media": {
        target: API_PROXY,
        changeOrigin: true,
      },
    },
  },
});
