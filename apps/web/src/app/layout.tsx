/** Root layout — Next.js 15 App Router. */
import type { Metadata } from "next";
import { getLocale, getMessages } from "next-intl/server";
import { NextIntlClientProvider } from "next-intl";

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
  const locale = await getLocale();
  const messages = await getMessages();

  return (
    <html lang={locale}>
      <body>
        <NextIntlClientProvider locale={locale} messages={messages}>
          {children}
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
