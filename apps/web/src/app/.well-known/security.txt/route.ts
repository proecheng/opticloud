import { buildSecurityTxt } from "@/lib/security-disclosure";

export function GET(): Response {
  return new Response(buildSecurityTxt(), {
    status: 200,
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
    },
  });
}
