import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// The SPA is single-origin: in dev, Vite proxies all backend paths to the
// gateway (:8080), which fans out to the five module services. In production
// the same paths are served behind one reverse proxy.
const GATEWAY = process.env.GATEWAY_URL || "http://localhost:8080";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: GATEWAY, changeOrigin: true },
      "/pipeline": { target: GATEWAY, changeOrigin: true },
      "/services": { target: GATEWAY, changeOrigin: true },
      "/health": { target: GATEWAY, changeOrigin: true },
    },
  },
});
