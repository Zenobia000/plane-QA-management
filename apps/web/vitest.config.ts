import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    tsconfigPaths: true,
  },
  test: {
    environment: "node",
    setupFiles: ["./vitest.setup.ts"],
    include: ["core/**/*.spec.{ts,tsx}", "app/**/*.spec.{ts,tsx}"],
    clearMocks: true,
  },
});
