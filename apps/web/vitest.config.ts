import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    tsconfigPaths: true,
    alias: {
      // Mirrors vite.config.ts. This app runs on React Router, but code carried
      // over from the Next build still imports next/navigation, so a spec that
      // pulls in one of those modules fails to resolve without the same shim
      // the app is built with.
      "next/navigation": path.resolve(import.meta.dirname, "app/compat/next/navigation.ts"),
    },
  },
  test: {
    environment: "node",
    setupFiles: ["./vitest.setup.ts"],
    include: ["core/**/*.spec.{ts,tsx}", "app/**/*.spec.{ts,tsx}"],
    clearMocks: true,
  },
});
