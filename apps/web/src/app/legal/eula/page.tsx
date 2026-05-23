/** /legal/eula — bilingual legal shell, final text pending legal review. */
import { useTranslations } from "next-intl";

import { LegalShell } from "@/components/LegalShell";

export default function EulaPage(): JSX.Element {
  const t = useTranslations("legal.eula");
  return <LegalShell title={t("title")} body={t("body")} />;
}
