// @vitest-environment happy-dom

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  DEFAULT_LOCALE,
  LOCALE_COOKIE_NAME,
  LOCALE_STORAGE_KEY,
  ensureDocumentLocale,
  getAcceptLanguage,
  normalizeLocale,
  readLocaleFromCookie,
  readStoredLocale,
  writeStoredLocale,
} from "./locale";

describe("locale helpers", () => {
  afterEach(() => {
    window.localStorage.clear();
    document.cookie = `${LOCALE_COOKIE_NAME}=; path=/; max-age=0`;
    vi.restoreAllMocks();
  });

  it("normalizes only supported locale values", () => {
    expect(normalizeLocale("zh-CN")).toBe("zh-CN");
    expect(normalizeLocale("en-US")).toBe("en-US");
    expect(normalizeLocale("zh")).toBe(DEFAULT_LOCALE);
    expect(normalizeLocale(null)).toBe(DEFAULT_LOCALE);
  });

  it("reads locale from localStorage before cookie", () => {
    document.cookie = `${LOCALE_COOKIE_NAME}=zh-CN; path=/`;
    window.localStorage.setItem(LOCALE_STORAGE_KEY, "en-US");

    expect(readStoredLocale()).toBe("en-US");
    expect(getAcceptLanguage()).toBe("en-US");
  });

  it("falls back to cookie and then default", () => {
    expect(readStoredLocale()).toBe("zh-CN");

    document.cookie = `${LOCALE_COOKIE_NAME}=en-US; path=/`;
    expect(readStoredLocale()).toBe("en-US");
    expect(readLocaleFromCookie(`${LOCALE_COOKIE_NAME}=bad`)).toBe("zh-CN");
  });

  it("writes storage, cookie, and document lang", () => {
    writeStoredLocale("en-US");

    expect(window.localStorage.getItem(LOCALE_STORAGE_KEY)).toBe("en-US");
    expect(document.cookie).toContain(`${LOCALE_COOKIE_NAME}=en-US`);
    expect(document.documentElement.lang).toBe("en-US");
  });

  it("does not crash when storage write fails", () => {
    vi.spyOn(window.localStorage.__proto__, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });

    expect(() => writeStoredLocale("en-US")).not.toThrow();
    expect(document.documentElement.lang).toBe("en-US");
  });

  it("updates document lang explicitly", () => {
    ensureDocumentLocale("en-US");

    expect(document.documentElement.lang).toBe("en-US");
  });
});
