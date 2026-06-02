import { buildRssXml } from "@/lib/status-page";

export function GET(): Response {
  return new Response(buildRssXml(), {
    status: 200,
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8",
    },
  });
}
