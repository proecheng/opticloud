/** Public Status Page (Story 8.A.1, FR O1) — SSR, unauthenticated, Trust-Forward. */
import { PUBLIC_STATUS_MODEL } from "@/lib/status-page";

import { StatusPageView } from "./StatusPageView";

export const metadata = {
  title: "OptiCloud Status",
  description: "Public OptiCloud service status, incident history, and RSS feed.",
};

export default function StatusPage(): JSX.Element {
  return <StatusPageView model={PUBLIC_STATUS_MODEL} />;
}
