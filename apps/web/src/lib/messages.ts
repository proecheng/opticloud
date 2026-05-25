import enUS from "../../messages/en-US.json";
import zhCN from "../../messages/zh-CN.json";
import { DEFAULT_LOCALE, type Locale, normalizeLocale } from "./locale";

export const messagesByLocale = {
  "zh-CN": zhCN,
  "en-US": enUS,
} as const;

type Messages = typeof zhCN;

function resolvePath(messages: Messages, key: string): string {
  const value = key.split(".").reduce<unknown>((current, part) => {
    if (current && typeof current === "object" && part in current) {
      return (current as Record<string, unknown>)[part];
    }
    return undefined;
  }, messages);
  return typeof value === "string" ? value : key;
}

export function getMessages(locale: unknown): Messages {
  return messagesByLocale[normalizeLocale(locale)];
}

export function translate(locale: unknown, key: string): string {
  const normalized = normalizeLocale(locale);
  const localized = resolvePath(messagesByLocale[normalized], key);
  if (localized !== key || normalized === DEFAULT_LOCALE) return localized;
  return resolvePath(messagesByLocale[DEFAULT_LOCALE], key);
}

export function translateWithLocale(locale: Locale): (key: string) => string {
  return (key: string) => translate(locale, key);
}
