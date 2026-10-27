import {fileURLToPath} from "node:url";
import {defineConfig} from "vite";
import react from "@vitejs/plugin-react";

// Optional local backend. Preserve the browser Origin for backend admission checks.
const proxy = process.env.BAATCHIT_WS_TARGET
  ? {"/ws": {target: process.env.BAATCHIT_WS_TARGET, ws: true, changeOrigin: false}}
  : undefined;

export default defineConfig({
  root: fileURLToPath(new URL(".", import.meta.url)),
  plugins: [react()],
  publicDir: false,
  server: {host: "127.0.0.1", port: 8080, strictPort: true, proxy},
  preview: {
    host: "127.0.0.1", port: 8080, strictPort: true, proxy,
    // Exercise the same policy as the production gateway when previewing a build.
    headers: {
      "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
      "X-Content-Type-Options": "nosniff",
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    // The production CSP permits same-origin assets, without data: images.
    assetsInlineLimit: 0,
  },
});
