import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vite";

// Build straight into the FastAPI static dir; the committed dist/ keeps the
// Python server and Docker image Node-free at runtime.
export default defineConfig({
  plugins: [svelte()],
  base: "/static/dist/",
  build: {
    outDir: "../api/static/dist",
    emptyOutDir: true,
  },
  server: {
    // `npm run dev` proxies API calls to the FastAPI server.
    proxy: { "/api": "http://localhost:8000" },
  },
});
