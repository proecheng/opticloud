// Web app Tailwind config — re-exports packages/ui config tokens
import type { Config } from "tailwindcss";
import uiConfig from "../../packages/ui/tailwind.config";

const config: Config = {
  ...uiConfig,
  content: [
    "./src/**/*.{ts,tsx}",
    "../../packages/ui/src/**/*.{ts,tsx}",
  ],
};

export default config;
