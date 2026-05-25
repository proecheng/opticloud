/** Root layout — Next.js 15 App Router. */
import { getLocale, getMessages } from "next-intl/server";
import { NextIntlClientProvider } from "next-intl";
import type { Metadata } from "next";

import { LocaleProvider } from "@/components/LocaleProvider";
import { DEFAULT_LOCALE, normalizeLocale } from "@/lib/locale";

import "./globals.css";

export const metadata: Metadata = {
  title: "OptiCloud — 通用优化与预测云",
  description: "让懂业务的工程师 5 分钟用上 Gurobi/TimeGPT 级算法",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}): Promise<JSX.Element> {
  const locale = normalizeLocale(await getLocale());
  const messages = await getMessages();

  return (
    <html lang={DEFAULT_LOCALE}>
      <body>
        <NextIntlClientProvider locale={locale} messages={messages}>
          <LocaleProvider initialLocale={locale}>{children}</LocaleProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
