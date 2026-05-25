import { cookies } from "next/headers";
import { getRequestConfig } from "next-intl/server";

import { LOCALE_COOKIE_NAME, normalizeLocale } from "@/lib/locale";
import { getMessages } from "@/lib/messages";

export default getRequestConfig(async () => {
  const cookieStore = await cookies();
  const locale = normalizeLocale(cookieStore.get(LOCALE_COOKIE_NAME)?.value);

  return {
    locale,
    messages: getMessages(locale),
  };
});
