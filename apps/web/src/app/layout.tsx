/** Root layout — Next.js 15 App Router. */
import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "OptiCloud — 通用优化与预测云",
  description: "让懂业务的工程师 5 分钟用上 Gurobi/TimeGPT 级算法",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}): JSX.Element {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
