import { afterEach, describe, expect, it, vi } from "vitest";

import {
  DEFAULT_LOCALE,
  LOCALE_COOKIE_NAME,
  buildLocaleCookie,
  getClientLocale,
  getCookieValue,
  localeFromAcceptLanguage,
  normalizeLocale,
  resolveLocale,
} from "./locales";

describe("locale helpers", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("normalizes supported locale aliases only", () => {
    expect(normalizeLocale("zh_CN")).toBe("zh-CN");
    expect(normalizeLocale("en")).toBe("en-US");
    expect(normalizeLocale("fr-FR")).toBeNull();
  });

  it("resolves cookie before Accept-Language and falls back to zh-CN", () => {
    expect(
      resolveLocale({
        cookieLocale: "en-US",
        acceptLanguage: "zh-CN,zh;q=0.9",
      }),
    ).toBe("en-US");
    expect(resolveLocale({ cookieLocale: "invalid" })).toBe(DEFAULT_LOCALE);
  });

  it("parses weighted Accept-Language values", () => {
    expect(localeFromAcceptLanguage("fr-FR, en-US;q=0.9, zh-CN;q=0.8")).toBe(
      "en-US",
    );
    expect(localeFromAcceptLanguage("fr-FR")).toBeNull();
  });

  it("reads and builds the locale cookie", () => {
    const cookie = buildLocaleCookie("en-US");

    expect(cookie).toContain(`${LOCALE_COOKIE_NAME}=en-US`);
    expect(cookie).toContain("Path=/");
    expect(cookie).toContain("SameSite=Lax");
    expect(getCookieValue(`a=1; ${LOCALE_COOKIE_NAME}=zh-CN`, LOCALE_COOKIE_NAME)).toBe(
      "zh-CN",
    );
  });

  it("uses document cookie in browser and zh-CN in non-browser tests", () => {
    expect(getClientLocale()).toBe("zh-CN");

    vi.stubGlobal("document", {
      cookie: `${LOCALE_COOKIE_NAME}=en-US`,
    });
    vi.stubGlobal("navigator", {
      languages: ["zh-CN"],
    });

    expect(getClientLocale()).toBe("en-US");
  });
});
