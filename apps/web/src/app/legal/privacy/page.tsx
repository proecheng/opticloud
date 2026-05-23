/** /legal/privacy — bilingual legal shell, final text pending legal review. */
import { useTranslations } from "next-intl";

import { LegalShell } from "@/components/LegalShell";

export default function PrivacyPage(): JSX.Element {
  const t = useTranslations("legal.privacy");
  return <LegalShell title={t("title")} body={t("body")} />;
}
