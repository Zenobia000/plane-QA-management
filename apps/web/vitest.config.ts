import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    tsconfigPaths: true,
  },
  test: {
    environment: "node",
    include: ["core/**/*.spec.{ts,tsx}", "app/**/*.spec.{ts,tsx}"],
    clearMocks: true,
  },
});
