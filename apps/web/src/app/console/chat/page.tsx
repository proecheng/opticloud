"use client";
/** /console/chat — internal beta ChatInterface dogfood surface (Story 4.C.6). */

import Link from "next/link";
import { useState } from "react";

import {
  ChatInterface,
  type ChatInterfaceFileSelectionResult,
  type ChatInterfaceSendRequest,
  type ChatInterfaceSendResult,
} from "@opticloud/ui";

import {
  discardChatRecovery,
  replaceChatRecoveryRows,
  selectChatFile,
  sendInternalBetaChatMessage,
  streamInternalBetaChatMessage,
  type InternalBetaCredentials,
} from "@/lib/chat";

export default function ConsoleChatPage(): JSX.Element {
  const [tenant, setTenant] = useState("");
  const [user, setUser] = useState("");
  const [token, setToken] = useState("");

  const credentials = (): InternalBetaCredentials => ({
    tenant: tenant.trim(),
    user: user.trim(),
    token,
  });

  const sendWithFallback = async (
    request: ChatInterfaceSendRequest,
  ): Promise<ChatInterfaceSendResult> => {
    const base = {
      credentials: credentials(),
      message: request.message,
      locale: request.locale,
      fileContexts: request.fileContexts,
      whatIfContext: request.whatIfContext,
    };

    return {
      mode: "stream",
      events: streamWithJsonFallback(streamInternalBetaChatMessage(base), base),
    };
  };

  return (
    <main className="min-h-screen bg-background">
      <header className="border-b border-border bg-background">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-6 py-4">
          <Link href="/" className="flex items-center gap-2">
            <div className="h-7 w-7 rounded bg-primary" />
            <span className="font-semibold">OptiCloud</span>
          </Link>
          <nav className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
            <Link href="/console/predictions" className="text-muted-foreground hover:text-foreground">
              预测
            </Link>
            <Link href="/console/excel" className="text-muted-foreground hover:text-foreground">
              Excel
            </Link>
            <Link
              href="/console/data-exports"
              className="text-muted-foreground hover:text-foreground"
            >
              数据导出
            </Link>
          </nav>
        </div>
      </header>

      <section className="mx-auto grid max-w-6xl gap-4 px-6 py-6 lg:grid-cols-[280px_1fr]">
        <aside className="space-y-4 rounded-md border border-border bg-background p-4">
          <div>
            <h1 className="text-lg font-semibold">Chat internal beta</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              仅连接受保护 internal beta Chat endpoint。
            </p>
          </div>
          <label className="block">
            <span className="mb-1 block text-sm font-medium">Tenant</span>
            <input
              aria-label="Tenant"
              value={tenant}
              onChange={(event) => setTenant(event.target.value)}
              className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              placeholder="research-staging"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-sm font-medium">User</span>
            <input
              aria-label="User"
              value={user}
              onChange={(event) => setUser(event.target.value)}
              className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              placeholder="scholar-a"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-sm font-medium">Token</span>
            <input
              aria-label="Token"
              type="password"
              value={token}
              onChange={(event) => setToken(event.target.value)}
              className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              placeholder="internal beta token"
            />
          </label>
          <p className="text-xs text-muted-foreground">
            Token 只保存在当前页面状态中；刷新后会丢失。
          </p>
        </aside>

        <ChatInterface
          ariaLabel="console.chat.interface"
          onSendMessage={sendWithFallback}
          onSelectFile={(file): Promise<ChatInterfaceFileSelectionResult> =>
            selectChatFile(file)
          }
          onReplaceFailedRows={replaceChatRecoveryRows}
          onDiscardRecovery={discardChatRecovery}
        />
      </section>
    </main>
  );
}

async function* streamWithJsonFallback(
  events: AsyncIterable<import("@opticloud/ui").ChatInterfaceStreamEvent>,
  fallbackRequest: Parameters<typeof sendInternalBetaChatMessage>[0],
): AsyncIterable<import("@opticloud/ui").ChatInterfaceStreamEvent> {
  try {
    for await (const event of events) {
      yield event;
    }
  } catch {
    yield {
      type: "done",
      response: await sendInternalBetaChatMessage(fallbackRequest),
    };
  }
}
