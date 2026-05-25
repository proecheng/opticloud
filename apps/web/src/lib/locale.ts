export const SUPPORTED_LOCALES = ["zh-CN", "en-US"] as const;
export type Locale = (typeof SUPPORTED_LOCALES)[number];

export const DEFAULT_LOCALE: Locale = "zh-CN";
export const LOCALE_STORAGE_KEY = "opticloud:locale";
export const LOCALE_COOKIE_NAME = "opticloud_locale";

export const LOCALE_LABELS: Record<Locale, string> = {
  "zh-CN": "中文",
  "en-US": "English",
};

export function isSupportedLocale(value: unknown): value is Locale {
  return (
    typeof value === "string" &&
    SUPPORTED_LOCALES.includes(value as Locale)
  );
}

export function normalizeLocale(value: unknown): Locale {
  return isSupportedLocale(value) ? value : DEFAULT_LOCALE;
}

function safeDocumentCookie(): string {
  if (typeof document === "undefined") return "";
  try {
    return document.cookie;
  } catch {
    return "";
  }
}

export function readLocaleFromCookie(
  cookieValue: string,
  fallbackLocale: Locale = DEFAULT_LOCALE,
): Locale {
  const match = cookieValue
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${LOCALE_COOKIE_NAME}=`));
  if (!match) return fallbackLocale;
  const value = decodeURIComponent(match.split("=").slice(1).join("="));
  return isSupportedLocale(value) ? value : fallbackLocale;
}

export function readStoredLocale(
  fallbackLocale: Locale = DEFAULT_LOCALE,
): Locale {
  if (typeof window === "undefined") return fallbackLocale;
  try {
    const stored = window.localStorage.getItem(LOCALE_STORAGE_KEY);
    if (isSupportedLocale(stored)) return stored;
  } catch {
    // Storage can be unavailable in privacy modes and tests.
  }
  return readLocaleFromCookie(safeDocumentCookie(), fallbackLocale);
}

export function writeStoredLocale(locale: Locale): void {
  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
    } catch {
      // Ignore unavailable storage; cookie remains the shared fallback.
    }
  }

  if (typeof document !== "undefined") {
    document.cookie = `${LOCALE_COOKIE_NAME}=${encodeURIComponent(
      locale,
    )}; path=/; max-age=31536000; SameSite=Lax`;
    document.documentElement.lang = locale;
  }
}

export function ensureDocumentLocale(locale: Locale = readStoredLocale()): void {
  if (typeof document === "undefined") return;
  document.documentElement.lang = locale;
}

export function getAcceptLanguage(): Locale {
  return readStoredLocale();
}
