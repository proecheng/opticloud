// @vitest-environment happy-dom

import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { LocaleProvider } from "./LocaleProvider";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { LOCALE_STORAGE_KEY } from "@/lib/locale";

describe("LanguageSwitcher", () => {
  afterEach(() => {
    window.localStorage.clear();
  });

  it("renders both locale options and updates document lang", () => {
    render(
      <LocaleProvider>
        <LanguageSwitcher />
      </LocaleProvider>,
    );

    expect(screen.getByRole("button", { name: "中文" })).toBeTruthy();
    const english = screen.getByRole("button", { name: "English" });

    fireEvent.click(english);

    expect(document.documentElement.lang).toBe("en-US");
    expect(window.localStorage.getItem(LOCALE_STORAGE_KEY)).toBe("en-US");
    expect(english.getAttribute("aria-pressed")).toBe("true");
  });
});
