"use client";

import { LOCALE_LABELS, SUPPORTED_LOCALES, type Locale } from "@/lib/locale";
import { usePreferredLocale } from "./LocaleProvider";

export function LanguageSwitcher({
  className = "",
}: {
  className?: string;
}): JSX.Element {
  const { locale, setLocale } = usePreferredLocale();

  return (
    <div
      className={`inline-flex rounded-md border border-border bg-background p-1 text-xs shadow-sm ${className}`}
      role="group"
      aria-label="Language"
    >
      {SUPPORTED_LOCALES.map((option: Locale) => {
        const selected = option === locale;
        return (
          <button
            key={option}
            type="button"
            aria-pressed={selected}
            onClick={() => setLocale(option)}
            className={`min-h-touch rounded px-3 py-1.5 font-medium transition ${
              selected
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground"
            }`}
          >
            {LOCALE_LABELS[option]}
          </button>
        );
      })}
    </div>
  );
}
