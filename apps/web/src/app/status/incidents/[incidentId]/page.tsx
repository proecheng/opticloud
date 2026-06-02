import { notFound } from "next/navigation";

import { getPublishedP0Postmortem, PUBLIC_STATUS_MODEL } from "@/lib/status-page";

import { PostmortemPageView } from "./PostmortemPageView";

export const metadata = {
  title: "OptiCloud Incident Postmortem",
  description: "Public P0 incident postmortem and timeline.",
};

export default async function StatusIncidentPostmortemPage({
  params,
}: {
  params: Promise<{ incidentId: string }>;
}): Promise<JSX.Element> {
  const { incidentId } = await params;
  const incident = getPublishedP0Postmortem(PUBLIC_STATUS_MODEL, incidentId);
  if (!incident) {
    notFound();
  }

  return <PostmortemPageView incident={incident} components={PUBLIC_STATUS_MODEL.components} />;
}
