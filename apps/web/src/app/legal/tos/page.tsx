/** /legal/tos — bilingual legal shell, final text pending legal review. */
import { useTranslations } from "next-intl";

import { LegalShell } from "@/components/LegalShell";

export default function TermsPage(): JSX.Element {
  const t = useTranslations("legal.tos");
  return <LegalShell title={t("title")} body={t("body")} />;
}
