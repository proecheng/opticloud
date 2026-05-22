import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const srcDir = fileURLToPath(new URL("./src", import.meta.url));

export default defineConfig({
  plugins: [react()],
  test: {
    // Node env — lib tests are pure logic + File API (Node 20+ provides it).
    // Switch to happy-dom for component tests when those land in apps/web.
    environment: "node",
    globals: true,
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    // Test-time alias: production code uses /browser (real DOMParser), tests
    // use /node which doesn't need DOM. Both paths re-export the same default
    // function with the same signature.
    alias: {
      "@": srcDir,
      "read-excel-file/browser": "read-excel-file/node",
    },
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.test.{ts,tsx}", "src/**/*.spec.{ts,tsx}", "src/app/**/page.tsx"],
    },
  },
});
