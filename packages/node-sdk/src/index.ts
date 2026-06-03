export type ErrorDetail = Record<string, unknown> & {
  field_path?: string;
  value?: unknown;
  constraint?: string;
  remediation_hint_key?: string;
};

export interface OptiCloudHTTPErrorInput {
  status: number;
  type?: string;
  title?: string;
  detail?: string;
  instance?: string | null;
  errors?: unknown;
  next_action_url?: string | null;
  request_id?: string | null;
  trace_id?: string | null;
  raw?: Record<string, unknown>;
}

export class OptiCloudError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "OptiCloudError";
  }
}

export class OptiCloudHTTPError extends OptiCloudError {
  readonly status: number;
  readonly type: string;
  readonly title: string;
  readonly detail: string;
  readonly instance?: string | null;
  readonly errors: ErrorDetail[];
  readonly next_action_url?: string | null;
  readonly request_id?: string | null;
  readonly trace_id?: string | null;
  readonly raw: Record<string, unknown>;

  constructor(input: OptiCloudHTTPErrorInput) {
    const title = input.title ?? "";
    const detail = input.detail ?? "";
    super(`[${input.status}] ${title}: ${detail}`);
    this.name = "OptiCloudHTTPError";
    this.status = input.status;
    this.type = input.type ?? "about:blank";
    this.title = title;
    this.detail = detail;
    this.instance = input.instance;
    this.errors = Array.isArray(input.errors)
      ? cloneJsonCompatible(input.errors) as ErrorDetail[]
      : [];
    this.next_action_url = input.next_action_url;
    this.request_id = input.request_id;
    this.trace_id = input.trace_id;
    this.raw = isRecord(input.raw) ? cloneJsonCompatible(input.raw) as Record<string, unknown> : {};
  }

  locate(fieldPath: string): unknown {
    return this.errors.find((detail) => detail.field_path === fieldPath)?.value;
  }

  locateAll(fieldPath: string): unknown[] {
    return this.errors
      .filter((detail) => detail.field_path === fieldPath)
      .map((detail) => detail.value);
  }

  findConstraint(pattern: RegExp | string): ErrorDetail[] {
    const regex = typeof pattern === "string" ? new RegExp(pattern) : pattern;
    return this.errors.filter((detail) => {
      return typeof detail.constraint === "string" && regex.test(detail.constraint);
    });
  }

  remediationKeys(): string[] {
    return this.errors
      .map((detail) => detail.remediation_hint_key)
      .filter((key): key is string => typeof key === "string" && key.length > 0);
  }
}

export function parseOptiCloudErrorResponse(
  status: number,
  body: Record<string, unknown>,
): OptiCloudHTTPError {
  const title = typeof body.title === "string" ? body.title : "";
  const detail = typeof body.detail === "string" ? body.detail : "";
  const type = typeof body.type === "string" ? body.type : "about:blank";
  const instance =
    typeof body.instance === "string" || body.instance === null ? body.instance : undefined;
  const nextActionUrl =
    typeof body.next_action_url === "string" || body.next_action_url === null
      ? body.next_action_url
      : undefined;
  const requestId =
    typeof body.request_id === "string" || body.request_id === null ? body.request_id : undefined;
  const traceId =
    typeof body.trace_id === "string" || body.trace_id === null ? body.trace_id : undefined;

  return new OptiCloudHTTPError({
    status,
    type,
    title,
    detail,
    instance,
    errors: body.errors,
    next_action_url: nextActionUrl,
    request_id: requestId,
    trace_id: traceId,
    raw: body,
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function cloneJsonCompatible<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}
