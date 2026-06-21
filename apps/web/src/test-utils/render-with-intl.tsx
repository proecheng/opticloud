import { render, type RenderOptions, type RenderResult } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactElement, ReactNode } from "react";

import zhMessages from "@/i18n/messages/zh-CN.json";

function IntlTestProvider({ children }: { children: ReactNode }): JSX.Element {
  return (
    <NextIntlClientProvider locale="zh-CN" messages={zhMessages}>
      {children}
    </NextIntlClientProvider>
  );
}

export function renderWithIntl(
  ui: ReactElement,
  options?: Omit<RenderOptions, "wrapper">,
): RenderResult {
  return render(ui, { wrapper: IntlTestProvider, ...options });
}
