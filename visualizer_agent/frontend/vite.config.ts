import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// SAGE frontend dev server. Proxies /api and /ws to the FastAPI gateway (port 8000)
// so the browser talks to a single origin in development.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/health": { target: "http://localhost:8000", changeOrigin: true },
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
