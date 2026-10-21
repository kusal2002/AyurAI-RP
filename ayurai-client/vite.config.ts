import { resolve } from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig, loadEnv } from "vite"

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "")

  // Development proxy targets for the Component 2 and Component 3 services.
  // The Component 2 service does not enable CORS, so the browser reaches it
  // through this same-origin proxy during local development.
  const c2Target = env.C2_PROXY_TARGET || "http://127.0.0.1:8000"
  const c3Target = env.C3_PROXY_TARGET || "http://127.0.0.1:8003"
  const c4Target = env.C4_PROXY_TARGET || "http://127.0.0.1:8004"
  const c1Target = env.C1_PROXY_TARGET || "http://127.0.0.1:8001"

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@": resolve(import.meta.dirname, "./src"),
      },
    },
    server: {
      proxy: {
        "/c1-api": {
          target: c1Target,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/c1-api/, ""),
        },
        "/c2-api": {
          target: c2Target,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/c2-api/, ""),
        },
        "/c3-api": {
          target: c3Target,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/c3-api/, ""),
        },
        "/c4-api": {
          target: c4Target,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/c4-api/, ""),
        },
      },
    },
  }
})
