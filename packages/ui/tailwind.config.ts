// OptiCloud Tailwind v3 config — Story 0.10 + UX-DR4 Brand & Visual System
// Constraint C22: v1 期间锁 Tailwind v3.4+；v4 升级 v1.5+ (P77 Migration Window)
//
// Tokens source: UX Spec Step 6 Design System Foundation + Step 8 Visual Foundation
// - Primary: #2D5BA8 Olympics Winner
// - Dark Mode: #0D1117 GitHub-aligned + Dark Primary #4A77BB
// - Typography: Inter Variable + 思源黑体 + Sarasa Gothic Mono
// - 70 tokens (color / typography / spacing / radius / shadow / animation)

import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./src/**/*.{ts,tsx}", "./.storybook/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // ===== Brand (UX-DR4) — Olympics Winner blue =====
        primary: {
          DEFAULT: "#2D5BA8", // Brand Primary v1
          foreground: "#FFFFFF",
          50: "#EEF2FA",
          100: "#D5DFEF",
          200: "#A7C0DE",
          300: "#79A1CD",
          400: "#4B81BC",
          500: "#2D5BA8", // base
          600: "#244988",
          700: "#1B3768",
          800: "#122548",
          900: "#091228",
        },
        // Dark Mode Primary (UX Spec Step 8)
        "primary-dark": "#4A77BB",
        // ===== Semantic =====
        success: { DEFAULT: "#0F9D58", foreground: "#FFFFFF" },
        warning: { DEFAULT: "#F4B400", foreground: "#1F2937" },
        danger: { DEFAULT: "#DB4437", foreground: "#FFFFFF" },
        // ===== Confidence (Story 4.B.4 + CRG14 visual brackets) =====
        confidence: {
          high: "#0F9D58", // ≥0.85 绿 "高置信"
          mid: "#F4B400", //  0.6-0.85 黄 "中置信"
          low: "#DB4437", // <0.6 红 "低置信请人工 review"
        },
        // ===== Neutral (GitHub-aligned dark mode #0D1117) =====
        background: "#FFFFFF",
        foreground: "#111827",
        muted: { DEFAULT: "#F3F4F6", foreground: "#6B7280" },
        border: "#E5E7EB",
        // Dark mode equivalents (UX Spec Step 8)
        "background-dark": "#0D1117", // GitHub-aligned
        "foreground-dark": "#E6EDF3",
        "muted-dark": { DEFAULT: "#161B22", foreground: "#9CA3AF" },
        "border-dark": "#30363D",
      },
      fontFamily: {
        sans: [
          "Inter Variable",
          "Inter",
          "思源黑体",
          "Source Han Sans SC",
          "PingFang SC",
          "Microsoft YaHei",
          "sans-serif",
        ],
        mono: [
          "Sarasa Gothic Mono",
          "SF Mono",
          "Monaco",
          "Consolas",
          "monospace",
        ],
      },
      spacing: {
        // Brand spacing scale (4px base; UX Spec Step 8)
        "0.5": "2px",
        "1": "4px",
        "2": "8px",
        "3": "12px",
        "4": "16px",
        "6": "24px",
        "8": "32px",
        "12": "48px",
        "16": "64px",
        "24": "96px",
      },
      borderRadius: {
        sm: "4px",
        DEFAULT: "8px",
        md: "8px",
        lg: "12px",
        xl: "16px",
        "2xl": "24px",
      },
      boxShadow: {
        sm: "0 1px 2px rgba(0, 0, 0, 0.06)",
        DEFAULT: "0 4px 8px rgba(45, 91, 168, 0.08)", // Brand-tinted
        md: "0 6px 12px rgba(45, 91, 168, 0.10)",
        lg: "0 12px 24px rgba(45, 91, 168, 0.14)",
        focus: "0 0 0 3px rgba(45, 91, 168, 0.40)", // a11y focus ring
      },
      animation: {
        // Restricted motion (UX Spec Step 8 Animation Discipline)
        "shimmer-pulse": "shimmer-pulse 1.5s ease-in-out infinite",
        "fade-in": "fade-in 200ms ease-out",
        "slide-up": "slide-up 250ms ease-out",
      },
      keyframes: {
        "shimmer-pulse": {
          "0%, 100%": { opacity: "0.6" },
          "50%": { opacity: "1" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "slide-up": {
          from: { transform: "translateY(8px)", opacity: "0" },
          to: { transform: "translateY(0)", opacity: "1" },
        },
      },
      // Touch target min (Story 13 AA5)
      minHeight: {
        touch: "44px",
      },
      minWidth: {
        touch: "44px",
      },
    },
  },
  plugins: [],
};

export default config;
