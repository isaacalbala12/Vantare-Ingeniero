import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node", // No necesita jsdom para tests de lógica pura
    globals: true,
    include: ["src/__tests__/**/*.test.ts"],
    setupFiles: ["src/__tests__/setup.ts"],
  },
});
