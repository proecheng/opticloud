export const SUPPORTED_LOCALES = ["zh-CN", "en-US"] as const;

export type AppLocale = (typeof SUPPORTED_LOCALES)[number];

export const DEFAULT_LOCALE: AppLocale = "zh-CN";
export const LOCALE_COOKIE_NAME = "opticloud-locale";
export const LOCALE_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 180;
export const REQUEST_LOCALE_HEADER = "x-opticloud-locale";

export function normalizeLocale(value: string | null | undefined): AppLocale | null {
  if (!value) return null;
  const normalized = value.trim().replace("_", "-").toLowerCase();
  if (normalized === "zh" || normalized === "zh-cn") return "zh-CN";
  if (normalized === "en" || normalized === "en-us") return "en-US";
  return null;
}

export function localeFromAcceptLanguage(
  acceptLanguage: string | null | undefined,
): AppLocale | null {
  if (!acceptLanguage) return null;
  const candidates = acceptLanguage
    .split(",")
    .map((part) => {
      const [tag = "", qValue] = part.trim().split(";q=");
      const quality = qValue ? Number.parseFloat(qValue) : 1;
      return {
        locale: normalizeLocale(tag),
        quality: Number.isFinite(quality) ? quality : 0,
      };
    })
    .filter((candidate): candidate is { locale: AppLocale; quality: number } =>
      Boolean(candidate.locale),
    )
    .sort((a, b) => b.quality - a.quality);
  return candidates[0]?.locale ?? null;
}

export function getCookieValue(
  cookieHeader: string | null | undefined,
  name: string,
): string | null {
  if (!cookieHeader) return null;
  const prefix = `${name}=`;
  const match = cookieHeader
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix));
  return match ? decodeURIComponent(match.slice(prefix.length)) : null;
}

export interface LocaleResolutionInput {
  explicitLocale?: string | null;
  cookieLocale?: string | null;
  acceptLanguage?: string | null;
}

export function resolveLocale({
  explicitLocale,
  cookieLocale,
  acceptLanguage,
}: LocaleResolutionInput = {}): AppLocale {
  return (
    normalizeLocale(explicitLocale) ??
    normalizeLocale(cookieLocale) ??
    localeFromAcceptLanguage(acceptLanguage) ??
    DEFAULT_LOCALE
  );
}

export function getClientLocale(): AppLocale {
  if (typeof document === "undefined") return DEFAULT_LOCALE;
  return resolveLocale({
    cookieLocale: getCookieValue(document.cookie, LOCALE_COOKIE_NAME),
    acceptLanguage:
      typeof navigator === "undefined" ? null : navigator.languages?.join(","),
  });
}

export function buildLocaleCookie(locale: AppLocale): string {
  return [
    `${LOCALE_COOKIE_NAME}=${encodeURIComponent(locale)}`,
    "Path=/",
    `Max-Age=${LOCALE_COOKIE_MAX_AGE_SECONDS}`,
    "SameSite=Lax",
  ].join("; ");
}
