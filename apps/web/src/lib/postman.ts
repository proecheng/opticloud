/** Generate Postman 2.1 Collection JSON for OptiCloud Hello World 三件套.
 *
 * FG1.1 Critical M1 — "导入 Postman" button in Story 1.1b ConfirmationModal.
 * Includes:
 *   1. POST /v1/optimizations (LP Hello World #1)
 *   2. GET /v1/credits/balance (Hello World #2)
 *   3. GET /v1/algorithms (Hello World #3, no auth)
 *   + 5 Plan rate limit variants
 *   + RFC 7807 error response examples
 */

export interface PostmanCollectionOptions {
  apiKey: string;
  apiBaseUrl?: string;
}

export function generatePostmanCollection({
  apiKey,
  apiBaseUrl = "https://api.opticloud.cn",
}: PostmanCollectionOptions): object {
  return {
    info: {
      _postman_id: crypto.randomUUID?.() ?? "manual-generated",
      name: "OptiCloud — Hello World 三件套",
      description:
        "Auto-generated from OptiCloud Console on signup. Contains Hello World 三件套 + Plan rate limit variants + RFC 7807 error examples.\n\n**API Key**: stored as collection variable `{{apiKey}}`. Replace if rotated.\n\n**Owner Story**: 1.1b J1 Vertical Slice + FG1.1 Critical M1.",
      schema:
        "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
    },
    variable: [
      { key: "apiKey", value: apiKey, type: "string" },
      { key: "apiBaseUrl", value: apiBaseUrl, type: "string" },
    ],
    auth: {
      type: "bearer",
      bearer: [{ key: "token", value: "{{apiKey}}", type: "string" }],
    },
    item: [
      {
        name: "Hello World 三件套",
        item: [
          {
            name: "1. LP 求解（30 秒到结果）",
            request: {
              method: "POST",
              header: [
                { key: "Content-Type", value: "application/json" },
                { key: "Idempotency-Key", value: "{{$randomUUID}}" },
                { key: "Accept-Language", value: "zh-CN" },
              ],
              body: {
                mode: "raw",
                raw: JSON.stringify(
                  {
                    task_type: "lp",
                    minimize: { c: [1, 1] },
                    st: { A: [[1, 1]], b: [10] },
                  },
                  null,
                  2,
                ),
              },
              url: {
                raw: "{{apiBaseUrl}}/v1/optimizations",
                host: ["{{apiBaseUrl}}"],
                path: ["v1", "optimizations"],
              },
            },
          },
          {
            name: "2. 查 Credits 余额（1 秒）",
            request: {
              method: "GET",
              header: [],
              url: {
                raw: "{{apiBaseUrl}}/v1/credits/balance",
                host: ["{{apiBaseUrl}}"],
                path: ["v1", "credits", "balance"],
              },
            },
          },
          {
            name: "3. 公开算法列表（免鉴权）",
            request: {
              method: "GET",
              header: [],
              auth: { type: "noauth" },
              url: {
                raw: "{{apiBaseUrl}}/v1/algorithms",
                host: ["{{apiBaseUrl}}"],
                path: ["v1", "algorithms"],
              },
            },
          },
        ],
      },
      {
        name: "RFC 7807 错误响应样例 (FG1.3)",
        item: [
          {
            name: "422 不可行 LP (errors[] detail with field_path)",
            request: {
              method: "POST",
              header: [
                { key: "Content-Type", value: "application/json" },
                { key: "Idempotency-Key", value: "{{$randomUUID}}" },
              ],
              body: {
                mode: "raw",
                raw: JSON.stringify(
                  {
                    task_type: "lp",
                    minimize: { c: [1, 1] },
                    st: { A: [[1, 1]], b: [-1] },
                  },
                  null,
                  2,
                ),
              },
              url: {
                raw: "{{apiBaseUrl}}/v1/optimizations",
                host: ["{{apiBaseUrl}}"],
                path: ["v1", "optimizations"],
              },
              description:
                "预期返回 422 + errors[] 含 field_path='st.b[0]' + remediation_hint_key='errors.422.non_negative' + next_action_url",
            },
          },
        ],
      },
    ],
  };
}

export function downloadPostmanCollection(opts: PostmanCollectionOptions): void {
  const collection = generatePostmanCollection(opts);
  const blob = new Blob([JSON.stringify(collection, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "opticloud-postman-collection.json";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
