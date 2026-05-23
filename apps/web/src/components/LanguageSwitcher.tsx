"use client";

import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";

import {
  type AppLocale,
  buildLocaleCookie,
  normalizeLocale,
} from "@/i18n/locales";

const OPTIONS: AppLocale[] = ["zh-CN", "en-US"];

export function LanguageSwitcher({ className = "" }: { className?: string }): JSX.Element {
  const router = useRouter();
  const locale = normalizeLocale(useLocale()) ?? "zh-CN";
  const t = useTranslations("common.language");

  const switchLocale = (nextLocale: AppLocale): void => {
    document.cookie = buildLocaleCookie(nextLocale);
    router.refresh();
  };

  return (
    <div
      className={`inline-flex items-center gap-1 rounded-md border border-border bg-background p-1 text-xs ${className}`}
      aria-label={t("aria")}
      data-testid="language-switcher"
    >
      {OPTIONS.map((option) => {
        const active = option === locale;
        return (
          <button
            key={option}
            type="button"
            onClick={() => switchLocale(option)}
            aria-pressed={active}
            className={
              "min-h-9 rounded px-2.5 font-medium transition " +
              (active
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground")
            }
          >
            {option === "zh-CN" ? t("zh") : t("en")}
          </button>
        );
      })}
    </div>
  );
}
