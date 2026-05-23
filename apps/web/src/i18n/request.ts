import { getRequestConfig } from "next-intl/server";
import { cookies, headers } from "next/headers";

import enMessages from "./messages/en-US.json";
import zhMessages from "./messages/zh-CN.json";
import {
  DEFAULT_LOCALE,
  LOCALE_COOKIE_NAME,
  type AppLocale,
  resolveLocale,
} from "./locales";

const messagesByLocale = {
  "zh-CN": zhMessages,
  "en-US": enMessages,
} satisfies Record<AppLocale, typeof zhMessages>;

function mergeMessages(
  fallback: Record<string, unknown>,
  localized: Record<string, unknown>,
): Record<string, unknown> {
  const result: Record<string, unknown> = { ...fallback };
  for (const [key, value] of Object.entries(localized)) {
    if (
      value &&
      typeof value === "object" &&
      !Array.isArray(value) &&
      result[key] &&
      typeof result[key] === "object" &&
      !Array.isArray(result[key])
    ) {
      result[key] = mergeMessages(
        result[key] as Record<string, unknown>,
        value as Record<string, unknown>,
      );
    } else {
      result[key] = value;
    }
  }
  return result;
}

export default getRequestConfig(async ({ requestLocale, locale }) => {
  const cookieStore = await cookies();
  const headerStore = await headers();
  const resolvedLocale = resolveLocale({
    explicitLocale: locale ?? (await requestLocale),
    cookieLocale: cookieStore.get(LOCALE_COOKIE_NAME)?.value,
    acceptLanguage: headerStore.get("accept-language"),
  });

  return {
    locale: resolvedLocale ?? DEFAULT_LOCALE,
    messages: {
      ...mergeMessages(
        zhMessages as Record<string, unknown>,
        messagesByLocale[resolvedLocale] as Record<string, unknown>,
      ),
    },
  };
});
