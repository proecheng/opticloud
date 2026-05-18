/** 404 page — UX Spec Step 9 Error Pages Direction "Recovery-Forward". */
import Link from "next/link";

import { EmptyState } from "@opticloud/ui";

export default function NotFound(): JSX.Element {
  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <EmptyState
        ariaLabel="page.not_found"
        icon="🔍"
        title="找不到这个页面"
        description="你可能复制了错误的链接，或者这个页面已被移除。"
        action={
          <Link
            href="/"
            className="min-h-touch rounded-md bg-primary px-4 py-2 text-primary-foreground hover:bg-primary-600"
          >
            返回首页
          </Link>
        }
      />
    </main>
  );
}
