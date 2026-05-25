// @vitest-environment happy-dom

import { afterEach, describe, expect, it } from "vitest";

import { LOCALE_STORAGE_KEY } from "./locale";
import { generatePostmanCollection } from "./postman";

function firstRequestHeaderValue(collection: object, key: string): string | null {
  const root = collection as {
    item: Array<{ item: Array<{ request: { header: Array<{ key: string; value: string }> } }> }>;
  };
  return (
    root.item[0]?.item[0]?.request.header.find((header) => header.key === key)
      ?.value ?? null
  );
}

describe("Postman collection locale", () => {
  afterEach(() => {
    window.localStorage.clear();
  });

  it("defaults Accept-Language to zh-CN", () => {
    const collection = generatePostmanCollection({ apiKey: "sk-test" });

    expect(firstRequestHeaderValue(collection, "Accept-Language")).toBe("zh-CN");
  });

  it("uses explicit en-US locale", () => {
    const collection = generatePostmanCollection({
      apiKey: "sk-test",
      locale: "en-US",
    });

    expect(firstRequestHeaderValue(collection, "Accept-Language")).toBe("en-US");
  });

  it("uses stored locale when locale option is omitted", () => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, "en-US");

    const collection = generatePostmanCollection({ apiKey: "sk-test" });

    expect(firstRequestHeaderValue(collection, "Accept-Language")).toBe("en-US");
  });
});
